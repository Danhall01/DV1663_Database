import mysql.connector as sql
from mysql.connector import errorcode
import random
from faker import Faker

#TODO Systems: maybe?
#? Inventory system
#? Friends system


VERBAL = False
MAX_CHARACTERS = 12
g_dbName = "GameData"
g_LoadbarCharacter = "█"

g_Classes = [
            "Fighter",
            "Cleric",
            "Ranger",
            "Wizard",
            "Sorcerer",
            "Warlock",
            "Bard",
            "Barbarian",
            "Druid"
]
g_activeUser = []
g_currentCharacter = []

def SQLConnect():
    return sql.connect(
        user='Dan',
        password='admin',
        # database='GameData',
        # host='127.0.0.1:3306'
        unix_socket= '/Applications/MAMP/tmp/mysql/mysql.sock'
    )

# DB and data creation
# ================================================== ==================================================
def _InitDatabase(session):
    retCode = 0
    try:
        session.execute("CREATE DATABASE {} DEFAULT CHARACTER SET 'utf8'".format(g_dbName))
    except sql.Error as err:
        print("\r[{}]\tFailed to create database '{}' with error: '{}'".format("w" if err.errno == 1007 else "-", g_dbName, err))
        retCode = -1
    return retCode

def _UseDatabase(session):
    retCode = 0
    try:
        session.execute("USE {};".format(g_dbName))
    except sql.Error as err:
        print("\r[w]\tFailed to set database with error: '{}'.".format(err))
        retCode = -1
    return retCode

def _InitTables(session):
    queries = [
        "CREATE TABLE Accounts ("                   \
            "Id INT NOT NULL AUTO_INCREMENT,"       \
            "Username varchar(255) NOT NULL,"       \
            "Password varchar(255) NOT NULL,"       \
            "FirstName varchar(255) NOT NULL,"      \
            "LastName varchar(255) NOT NULL,"       \
            "Active boolean NOT NULL DEFAULT True," \
            "PRIMARY KEY (Id)"                      \
        ");",
        
        "CREATE TABLE Servers ("                                    \
            "Name VARCHAR(255) NOT NULL,"                           \
            "Capacity INT NOT NULL,"                                \
            "ActivePlayers INT NOT NULL DEFAULT 0,"                 \
            "Status VARCHAR(255) NOT NULL DEFAULT \"Inactive\","    \
            "PRIMARY KEY (Name)"                                    \
        ");",
        
        # Guilds here are cross-server and hence are only limited by name
        "CREATE TABLE Guilds ("                                 \
            "Name VARCHAR(255) NOT NULL,"                       \
            "Members INT NOT NULL DEFAULT 0,"                   \
            "Score INT NOT NULL,"                               \
            "Active Boolean NOT NULL DEFAULT False,"            \
            "PRIMARY KEY (Name)"                                \
        ");",
        
        # PC here uses a "Composite Key" to let names be server bound
        "CREATE TABLE PlayerCharacters ("                           \
            "Name varchar(255) NOT NULL,"                           \
            "AccountId INT NOT NULL,"                               \
            "ServerId VARCHAR(255) NOT NULL,"                       \
            "GuildId VARCHAR(255) DEFAULT NULL,"                    \
            "IsLoggedIn Boolean NOT NULL DEFAULT False,"            \
            "Level INT NOT NULL DEFAULT 0,"                         \
            "Class varchar(255) NOT NULL,"                          \
            "FOREIGN KEY (AccountId) REFERENCES Accounts(Id),"      \
            "FOREIGN KEY (ServerId) REFERENCES Servers(Name),"      \
            "FOREIGN KEY (GuildId) REFERENCES Guilds(Name),"        \
            "CONSTRAINT CharacterId PRIMARY KEY (Name,ServerId)"    \
        ");"
        

    ]
    retCode = 0
    for query in queries:
        try:
            if VERBAL:
                print("\r[d]\tQuery: '{}'".format(query))
            session.execute(query)
        except sql.Error as err:
            print("\r[{}]\tFailed to create tables with error: '{}'".format("w" if err.errno == 1050 else "-", err))
            retCode = -1
        if retCode != 0:
            break
    return retCode

def _InitTriggers(session):
    tQueries = [
        # Updates the server count for logged in players
        "CREATE TRIGGER onCreation "                                     \
        "AFTER INSERT ON PlayerCharacters "                              \
        "FOR EACH ROW "                                                  \
        "BEGIN "                                                         \
            "IF new.IsLoggedIn = True THEN "                             \
                "UPDATE servers "                                        \
                "SET servers.ActivePlayers = servers.ActivePlayers + 1 " \
                "WHERE servers.Name = NEW.ServerId; "                    \
            "END IF; "                                                   \
        "END",

        # Updates the server upon a character being logged in or out
        "CREATE TRIGGER onLogInOut "                                                             \
        "AFTER UPDATE ON PlayerCharacters "                                                      \
        "FOR EACH ROW "                                                                          \
        "BEGIN "                                                                                 \
            "IF old.IsLoggedIn != new.IsLoggedIn THEN "                                          \
                "UPDATE servers "                                                                \
                "SET servers.ActivePlayers = servers.ActivePlayers + (NEW.IsLoggedIn * 2 - 1) "  \
                "WHERE servers.Name = NEW.ServerId; "                                            \
            "END IF;"                                                                            \
        "END",
        
        # On joining / leaving server, update status
        "CREATE TRIGGER updateServerStatus "                        \
        "BEFORE UPDATE ON Servers "                                 \
        "FOR EACH ROW "                                             \
        "updateServerStatus:BEGIN "                                 \
            "IF NEW.Status = \"Maintenance\" THEN "                 \
                "LEAVE updateServerStatus;"                         \
            "END IF;"                                               \
            "IF New.ActivePlayers = 0 THEN "                        \
                "SET New.Status = \"Inactive\";"                    \
            "ELSEIF NEW.ActivePlayers / NEW.Capacity < 0.30 THEN "  \
                "SET New.Status = \"Low\";"                         \
            "ELSEIF NEW.ActivePlayers / NEW.Capacity < 0.60 THEN "  \
                "SET New.Status = \"Medium\";"                      \
            "ELSEIF NEW.ActivePlayers / NEW.Capacity < 0.90 THEN "  \
                "SET New.Status = \"High\";"                        \
            "ELSE "                                                 \
                "SET New.Status = \"Full\";"                        \
            "END IF;"                                               \
        "END;",
        
        # On joining/leaving guilds, update member count
        "CREATE TRIGGER updateGuildMembers "                \
        "BEFORE UPDATE ON PlayerCharacters "                \
        "FOR EACH ROW "                                     \
        "BEGIN "                                            \
            "UPDATE Guilds "                                \
                "SET Guilds.Members = Guilds.Members + 1 "  \
                "WHERE NEW.GuildId = Guilds.Name;"          \
            "UPDATE Guilds "                                \
                "SET Guilds.Members = Guilds.Members - 1 "  \
                "WHERE OLD.GuildId = Guilds.Name;"          \
        "END;",
        
        # Set guild status based on member count
        "CREATE TRIGGER guildStatusUpdate " \
        "BEFORE UPDATE ON Guilds "          \
        "FOR EACH ROW "                     \
        "Begin "                            \
            "IF NEW.Members = 0 THEN "      \
                "SET NEW.Active = False;"   \
            "ELSEIF NEW.Members > 0 THEN "  \
                "SET NEW.Active = True;"    \
            "END IF;"                       \
        "END;",
        
        # Update guild score when players level up and / or join/leave a guild
        "CREATE TRIGGER guildScoreUpdate "          \
        "AFTER UPDATE ON PlayerCharacters "         \
        "FOR EACH ROW "                             \
        "BEGIN "                                    \
            "UPDATE Guilds g "                      \
            "SET g.score = ( "                      \
                "SELECT COALESCE(SUM(Level), 0) "   \
                "FROM PlayerCharacters "            \
                "WHERE GuildId = NEW.GuildId "      \
                "OR GuildId = OLD.GuildId "         \
            ") * 2 "                                \
            "WHERE g.Name = NEW.GuildId "           \
            "OR g.Name = OLD.GuildId;"              \
        "END;"
    ]
    retCode = 0
    for query in tQueries:
        try:
            if VERBAL:
                print("\r[d]\tTrigger: '{}'".format(query))
            session.execute(query)
        except sql.Error as err:
            print("\r[{}]\tFailed to add trigger with error: '{}'".format("w", err))
            retCode = -1
        if retCode != 0:
            break
    return retCode
 
def _SafeQuery(session, query, silent=False):
    # Ensure Connection to db
    if _UseDatabase(session) != 0:
        return -1
    
    # Perform query
    retCode = 0
    try:
        session.execute(query)
    except sql.Error as err:
        if not silent:
            print("\r[w]\tQuery '{}' failed with error: '{}'".format(query, session))
        retCode = -1
    return retCode

def CreateDB(session, *void):    
    if _InitDatabase(session) != 0:
        return -1
    if _UseDatabase(session) != 0:
        return -1
    if _InitTables(session) != 0:
        return -1
    if _InitTriggers(session) != 0:
        return -1
    print("\r[+]\tCreated Database")
    return 0

def DeleteDB(session, *void):
    retCode = 0
    try:
        session.execute("DROP DATABASE {}".format(g_dbName))
        print("\r[+]\tDeleted Database")
    except sql.Error as err:
        print("\r[w]\tCould not delete database, error: '{}'".format(err))
        retCode = -1
    return retCode 

def PopulateTables(session, connection):
    if _UseDatabase(session) != 0:
        return -1
    if _SafeQuery(session, "SELECT * FROM SERVERS;") != 0:
        return -1
    if len(session.fetchall()) > 0:
        print("\r[w]\tTables already contain data, use the Repopulate option to re-generate data.")
        return -1
    
    # Load bar
    print("\r[+]\tGenerating data for tables...")
    print("\r|{}|".format("-"*50),end="")
    print("\r|", end="", flush=True)
    
    
    # Fake data generator
    fData = Faker()
    
    numServers = random.randint(2, 5)
    serverNames = [fData.unique.country() for i in range(numServers * 15)]
    for i, name in enumerate(serverNames):
        if CreateServer(session, connection, name, random.randint(64, 256), silent=True) != 0:
            return -1
        if i % numServers == 0:
            print("{}".format(g_LoadbarCharacter), end="", flush=True)
    
    numGuilds = random.randint(2, 20)
    guildNames = [fData.unique.city() for i in range(numGuilds * 15)]
    for i, name in enumerate(guildNames):
        if CreateGuild(session, connection, name) != 0:
            return -1
        if (i % numGuilds == 0):
            print("{}".format(g_LoadbarCharacter), end="", flush=True)
    
    # Insert Admin Account
    if CreateAccount(session, connection, "Admin", "Root", "Daniel", "Häll") != 0:
        return -1
    
    numAccounts = random.randint(25, 150)
    for i in range(numAccounts * 20):
        # uid starts at 2 (1 without admin above)
        uid = i + 2
        CreateAccount(session, connection,
            fData.street_name(),
            fData.password(),
            fData.first_name(),
            fData.last_name(),
        )
        if not fData.boolean():
            SetUserStatus(session, connection, uid, False, silent=True)

        numCharacters = random.randint(1, MAX_CHARACTERS)
        for _ in range(numCharacters):
            while True:
                nameChoice = fData.name()
                serverChoice = random.choice(serverNames)
                if CreateCharacter(session, connection,
                                  nameChoice, 
                                  uid, 
                                  serverChoice, 
                                  random.choice(g_Classes),
                                  silent=True) != 0:
                    continue
                if LevelUp(session,connection, nameChoice, serverChoice, random.randint(0, 19)) != 0:
                    return -1
                
                # Return values here are only relevant to UI
                if fData.boolean():
                    LogInCharacter(session, connection, uid, nameChoice, serverChoice, silent=True)
                if fData.boolean():
                    JoinGuild(session, connection, nameChoice, serverChoice, random.choice(guildNames))
                break
                
        if (i % numAccounts == 0):
            print("{}".format(g_LoadbarCharacter), end="", flush=True)
    print("\r\n[+]\tFinished generating data...", flush=True)
    return 0

def RePopulateTables(session, connection):
    if DeleteDB(session) != 0:
        return -1
    if CreateDB(session) != 0:
        return -1
    return PopulateTables(session, connection)

def ClearData(session, *void):
    if DeleteDB(session) != 0:
        return -1
    if CreateDB(session) != 0:
        return -1
# ================================================== ==================================================

# ======================= Helper functions
def Fallthrough(arg):
    return arg
def NullFunc(*void):
    pass
def GetInput_s(inputstr, castfunc=Fallthrough):
    value = 0
    while True:
        try:
            value = castfunc(input(inputstr))
            if value == None:
                raise
            break
        except:
            print("Invalid input, try again")
    return value

# ======================= User
def LogInAccount(session, connection, userId=None, userName=None, password=None, silent=False):
    if userName == None:
        userName = GetInput_s("Enter Username: ")
    if userId == None:
        userId = GetInput_s("Enter User Id (Digits after '#'): ", int)
    if password == None:
        password = GetInput_s("Enter Password: ")
    
    query = "SELECT * FROM Accounts "\
        "WHERE Accounts.Id = {} "\
        "AND Accounts.Username = \"{}\" "\
        "AND Accounts.Password = \"{}\";"\
        "".format(userId, userName, password)
    if _SafeQuery(session, query) != 0:
        return -1
    
    global g_activeUser
    result = session.fetchall()
    if not result or len(result) > 1:
        if not silent:
            print("\r[-]\tInvalid username or password")
        return -1
    g_activeUser = result[0]
    
    if not silent:
        print("\r[+]\tSuccessfully logged in to user {}#{}".format(g_activeUser[1], g_activeUser[0]))
    return 0

def CreateAccount(session, connection, username=None, password=None, firstName=None, lastName=None, silent=False):
    while True:
        if username == None:
            username = GetInput_s("Enter Username: ")
        if password == None:
            password = GetInput_s("Enter Password: ")
        if firstName == None:
            firstName = GetInput_s("Enter First Name: ")
        if lastName == None:
            lastName = GetInput_s("Enter Last Name: ")
        print("\033[H\033[J", end="")
        if GetInput_s("Is this information correct?\n"\
                      "Username: {}\n"\
                      "Password: {}\n"\
                      "First Name: {}\n"\
                      "Last Name: {}\n"\
                      "Confirm (y/n): "\
                        "".format(username, password, firstName, lastName),
                      lambda arg : arg if arg == "y" or arg == "n" else None) == 'n':
            username = None
            password = None
            firstName = None
            lastName = None
        break
    
    query = "INSERT INTO Accounts VALUES (0, \"{}\", \"{}\", \"{}\", \"{}\", True);"\
        "".format(
                username,
                password,
                firstName,
                lastName,
            )
    if _SafeQuery(session, query) != 0:
        return -1
    connection.commit()
    
    queryUpdateUserLocal = "SELECT * FROM Accounts ORDER BY Id DESC LIMIT 1;"
    if _SafeQuery(session, queryUpdateUserLocal) != 0:
        return -1
    global g_activeUser
    g_activeUser = session.fetchall()[0]
    if not silent:
        print("\r[+]\tSuccessfully created User {}#{}".format(g_activeUser[1], g_activeUser[0]))
        print("\r[+]\tSuccessfully logged in to user {}#{}".format(g_activeUser[1], g_activeUser[0]))
    return 0

# Create / Delete Characters
def CreateCharacter(session, connection, userId, characterName, server, className, silent=False):
    # Check if creation is possible
    queryCharacterAmount = "SELECT COUNT(*) FROM playercharacters "\
        "WHERE playercharacters.AccountId = {};"\
        "".format(userId)
    if _SafeQuery(session, queryCharacterAmount) != 0:
        return -1
    if session.fetchall()[0][0] >= MAX_CHARACTERS:
        if not silent:
            print("\r[w]\tUnable to create character, character limit on accout has been reached")
        return -1
    
    # Create Character
    query = "INSERT INTO PlayerCharacters VALUES (\"{}\", {}, \"{}\", {}, {}, {}, \"{}\");"\
        "".format(
                characterName,  # Character name
                userId,           # Account id
                server,         # Server
                "NULL",         # Guild
                False,          # Logged in
                1,              # Level
                className       # Class
                )
    if _SafeQuery(session, query, silent=True) != 0:
        return -1
    connection.commit()
    return 0

def DeleteCharacter(session, connection, characterName, server, silent=False):
    pass

def LogInCharacter(session, connection, userId, characterName, server, silent=False):
    # Check if login is possible
    queryIsLoggedIn = "SELECT COUNT(*) FROM PlayerCharacters "\
                      "WHERE PlayerCharacters.AccountId = {} "\
                      "AND PlayerCharacters.IsLoggedIn = True;"\
                      "".format(userId)
    if _SafeQuery(session, queryIsLoggedIn) != 0:
        return -1
    if session.fetchall()[0][0] > 0:
        if not silent:
            print("\r[w]\tCould not log in, character is already online on this account")
        return -1

    queryServerCapacity = "SELECT Servers.Capacity, Servers.ActivePlayers, Servers.Status "\
                          "FROM Servers "\
                          "WHERE Servers.Name = \"{}\";"\
                          "".format(server)
    if _SafeQuery(session, queryServerCapacity) != 0:
        return -1
    capacity, players, status = session.fetchall()[0]
    if status == "Maintenance":
        if not silent:
            print("\r[w]\tCould not log in, server \"{}\" is currently in Maintenance mode".format(server))
        return -1
    if players + 1 > capacity:
        if not silent:
            print("\r[w]\tCould not log in, server \"{}\" is currently full".format(server))
        return -1
    
    # Log In
    queryLogIn = "UPDATE PlayerCharacters "\
                "SET PlayerCharacters.IsLoggedIn = True "\
                "WHERE PlayerCharacters.Name = \"{}\" "\
                "AND PlayerCharacters.ServerId = \"{}\""\
                "".format(characterName, server)
    if _SafeQuery(session, queryLogIn) != 0:
        return -1
    connection.commit()
    return 0

# Display all characters (n/12 used slots\n...) (Character JOIN server JOIN guild)
def DisplayAllCharactersAccount(session, void, userId):
    pass

# List all guilds (with cap (function), incremental (5 at a time))
def ListGuilds(session, *void):
    pass

def SearchGuild(session, void, guildName):
    pass

# Reserve Guildname (Set active with no members)
def ReserveGuildName(session, connection, guildName):
    pass

# Create Guild
def CreateGuild(session, connection, guildName):
    query = "INSERT INTO Guilds VALUES (\"{}\", 0, 0, False);"\
        "".format(guildName)
    if _SafeQuery(session, query) != 0:
        return -1
    connection.commit()
    return 0

# Join Guild
def JoinGuild(session, connection, characterName, server, guildName):
    query = "UPDATE PlayerCharacters " \
            "SET PlayerCharacters.GuildId = \"{}\" "    \
            "WHERE PlayerCharacters.Name = \"{}\" "     \
            "AND PlayerCharacters.ServerId = \"{}\";"   \
            "".format(guildName, characterName, server)
    if _SafeQuery(session, query) != 0:
        return -1
    connection.commit()
    return 0

# Leave Guild
def LeaveGuild(session, connection, characterName, server, guildName):
    pass

# Get My Guild Information (Amount of players, Online players & Who + their server)
def ListGuildMembers(session, void, guildName):
    pass

# Get Top Guild Information (Players JOIN Guild JOIN Server(guild[Low]:\nPlayers...))
def ListTopGuild(session, *void):
    pass


def LevelUp(session, connection, characterName, server, levels):
    query = "UPDATE PlayerCharacters " \
            "SET PlayerCharacters.Level = LEAST(PlayerCharacters.Level + GREATEST(0, {}), 20) "\
            "WHERE PlayerCharacters.Name = \"{}\" AND PlayerCharacters.ServerId = \"{}\";"\
            "".format(
                    levels,
                    characterName,
                    server)
    if _SafeQuery(session, query) != 0:
        return -1
    connection.commit()
    return 0


# ======================= Admin
def SetUserStatus(session, connection, userId=None, active=None, silent=False):
    if userId == None:
        userId = GetInput_s("Enter UserId (int): ", int)
        active = GetInput_s("Enter active status (1-active, 0-disabled): ", lambda arg: int(arg) if int(arg) == 0 or int(arg) == 1 else None)
    
    query = "UPDATE Accounts SET Accounts.Active = {} WHERE Accounts.Id = {}".format(active, userId)
    if _SafeQuery(session, query)!= 0:
        return -1
    connection.commit()
    if not silent:
        print("Changed user {}'s active status to {}".format(userId, "Inactive" if active == 0 else "Active"))
    return 0

def PurgeGuild(session, connection, guildName=None, silent=False):
    if guildName == None:
        guildName = GetInput_s("Enter Guild Name: ")
        confirm = GetInput_s(
            "WARNING: All members of guild \"{}\" will be removed and guild will become inactive, continue? (y/n): "\
                "".format(guildName)
                , lambda arg : arg if arg == "y" or arg == "n" else None)
        if confirm == "n":
            return -1
    
    query = "UPDATE PlayerCharacters SET PlayerCharacters.GuildId = NULL WHERE PlayerCharacters.GuildId = \"{}\";"\
        "".format(guildName)
    if _SafeQuery(session, query) != 0:
        return -1
    connection.commit()
    if not silent:
        print("\r[+]\tSuccessfully removed all players from guild \"{}\", guild is now Inactive. Use command \"Clean Guild Data\" to remove entry".format(guildName))
    return 0

def CleanGuildsData(session, connection, silent=False):
    queryCount = "SELECT COUNT(*) FROM Guilds WHERE Guilds.Active = False;"
    if _SafeQuery(session, queryCount) != 0:
        return -1
    try:
        count = session.fetchall()[0][0]
    except:
        count = 0
    if count == 0:
        return -1
    
    confirm = GetInput_s(
        "WARNING: All {} inactive guilds will be cleaned from the database, continue? (y/n): "\
            "".format(count)
            , lambda arg : arg if arg == "y" or arg == "n" else None)
    if confirm == "n":
        return -1
    
    query = "DELETE FROM Guilds WHERE Guilds.Active = False;"
    if _SafeQuery(session, query) != 0:
        return -1
    connection.commit()
    if not silent:
        print("\r[+]\tSuccessfully cleaned up inactive guilds")
    return 0

# ======================= Server
def ListServers(session, *void):
    query = "SELECT Name, Status FROM Servers;"
    if _SafeQuery(session, query) != 0:
        return -1
    li = session.fetchall()
    maxlen = max(len(server[0]) for server in li)
    for server in li:
        print("\rName: {}\tStatus: {}"\
            "".format(server[0].ljust(maxlen + 1), server[1]))
    return 0

def CreateServer(session, connection, serverName=None, capacity=256, silent=False):
    if serverName == None:
        serverName = GetInput_s("Enter server name: ")
    
    query = "INSERT INTO Servers VALUES (\"{}\", {}, 0, \"Inactive\");"\
        "".format(serverName, capacity)
    if _SafeQuery(session, query) != 0:
        return -1
    connection.commit()
    if not silent:
        print("\r[+]\tCreated server \"{}\"".format(serverName))
    return 0

def DeleteServer(session, connection, serverName=None, silent=False):
    if serverName == None:
        serverName = GetInput_s("Enter server name: ")
        confirm = GetInput_s(
            "WARNING: Server \"{}\" and all accociated players will be deleted, continue? (y/n): "\
                "".format(serverName)
                , lambda arg : arg if arg == "y" or arg == "n" else None)
        if confirm == "n":
            return -1
    
    # Clear server from players
    queryClear = "DELETE FROM Playercharacters WHERE Playercharacters.ServerId = \"{}\";"\
                "".format(serverName)
    if _SafeQuery(session, queryClear) != 0:
        return -1
    connection.commit()
    
    # Delete server
    query = "DELETE FROM Servers WHERE Servers.Name = \"{}\";"\
        "".format(serverName)
    if _SafeQuery(session, query) != 0:
        return -1
    connection.commit()
    if not silent:
        print("\r[+]\tDeleted server \"{}\"".format(serverName))
    return 0

def SetServerStatus(session, connection, serverName=None, silent=False):
    if serverName == None:
        serverName = GetInput_s("Enter server name: ")

    # Get server status
    queryStatus = "SELECT Status FROM Servers WHERE Servers.Name = \"{}\""\
                  "".format(serverName)
    if _SafeQuery(session, queryStatus) != 0:
        return -1
    fail = False
    try:
        status = session.fetchall()[0][0]
    except:
        if not silent:
            print("\r[w]\tCould not connect to server \"{}\", maybe check spelling?".format(serverName))
        fail = True
    if fail:
        return -1

    newStatus = "Maintenance" if status != "Maintenance" else "Inactive"
    
    # Log out every active player on server
    if newStatus == "Maintenance":
        queryLogout = "UPDATE PlayerCharacters SET PlayerCharacters.IsLoggedIn = False WHERE PlayerCharacters.ServerId = \"{}\";"\
            "".format(serverName)
        if _SafeQuery(session, queryLogout) != 0:
            return -1
        if not silent:
            print("\r[+]\tSuccessfully logged out every player on \"{}\"".format(serverName))
    
    # Change status
    query = "UPDATE Servers SET Servers.Status = \"{}\" WHERE Servers.Name = \"{}\";"\
        "".format(newStatus, serverName)
    if _SafeQuery(session, query) != 0:
        return -1
    connection.commit()
    if not silent:
        print("\r[+]\tServer \"{}\": status is now \"{}\"".format(serverName, newStatus))
    return 0

# ======================= Print
def StartHelp(*void):
    print("\033[H\033[J", end="")
    print(
        "Options:\n"              \
        "0: Quit\n"               \
        "1: Database Options\n"   \
        "2: User Options\n"       \
        "3: Admin Options\n"      \
        "4: Server Options\n"
    )
def DBHelp(*void):
    print("\033[H\033[J", end="")
    print(
        "Options:\n"                  \
        "0: Back\n"                   \
        "1: Create Database\n"        \
        "2: Delete Database\n"        \
        "3: Recreate Database\n"      \
        "4: Generate Table Data\n"    \
        "5: Re-Generate Table Data\n"
    )
def UserHelp(login, *void):
    print("\033[H\033[J", end="")
    if login:
        print("Logged in as: \"{} {}\" ({}#{})".format(login[3], login[4], login[1], login[0]))
    else:
        print("Not logged in")
    print(
        "Options:\n"\
        "0: Back\n" \
        "1: Login to Account\n"\
        "2: Create Account\n"\
            "\n"\
        "(Requires login):\n"
        "3: Create Character\n"\
        "4: Delete Character\n"\
        "5: Login to Character\n"\
        "6: Display all Characters on Account\n"\
            "\n"\
        "7: List all Guilds\n"\
        "8: Search for Guild\n"\
        "9: Reserve Guild Name\n"\
        "10: Create Guild\n"\
        "11: Join Guild\n"\
        "12: Leave Guild\n"\
        "13: List all Guild Member Characters\n"\
        "14: List Top Guild\n"
    )
def AdminHelp(*void):
    print("\033[H\033[J", end="")
    print(
        "Options:\n"\
        "0: Back\n"\
        "1: Set User Status\n"\
        "2: Purge Guild\n"\
        "3: Clean Guild Data\n"
    )
def ServerHelp(*void):
    print("\033[H\033[J", end="")
    print(
        "Options:\n"\
        "0: Back\n" \
        "1: List all servers\n"\
        "2: Create Server\n"\
        "3: Delete Server\n"\
        "4: Toggle Maintenance Mode\n"
    )

# ======================= Main
if __name__ == "__main__":
    connection = SQLConnect()
    session = connection.cursor()
    
    DBOptions = {
        # Option "1: Init Database"
        1: CreateDB,
        # Option "2: Delete Database"
        2: DeleteDB,
        # Option "3: Delete All Data"
        3: ClearData,
        # Option "4: Generate Data"
        4: PopulateTables,
        # Option "5: Re-Generate Data"
        5: RePopulateTables,
        # Option "6: Help"
        6: DBHelp
    }
    UserOptions = {
        1: LogInAccount,
        2: CreateAccount,
        
        3: CreateCharacter,
        4: DeleteCharacter,
        5: LogInCharacter,
        6: DisplayAllCharactersAccount,
        
        7: ListGuilds,
        8: SearchGuild,
        9: ReserveGuildName,
        10: CreateGuild,
        11: JoinGuild,
        12: LeaveGuild,
        13: ListGuildMembers,
        14: ListTopGuild,
        
        15: UserHelp
    }
    AdminOptions = {
        1: SetUserStatus,
        2: PurgeGuild,
        3: CleanGuildsData,
        4: AdminHelp
    }
    ServerOptions = {
        1: ListServers,
        2: CreateServer,
        3: DeleteServer,
        4: SetServerStatus,
        5: ServerHelp
    }
    StartChoices = {
        # Option "1: Modify Database"
        1: DBOptions,
        
        # Option "2: Login To Account (User)"
        2: UserOptions,
        
        # Option "3: Admin Login"
        3: AdminOptions,
        
        # Option "4: Modify Servers"
        4: ServerOptions,
        
        # Option "5: Help"
        5: StartHelp
    }
    
    option = StartChoices
    while True:
        maxval = max(option)
        option.get(maxval, NullFunc)(g_activeUser)
        try:
            cmd = int(input("Enter input (int): "))
            if cmd >= maxval:
                raise
        except:
            print("\r[w] Invalid Input: Only the displayed arguments are valid input.")
            input("Press any key to continue...")
            continue
        
        if cmd == 0:
            if option == StartChoices:
                break
            option = StartChoices
            StartHelp()
            continue
        
        if option == StartChoices and cmd != maxval:
            option = StartChoices.get(cmd, StartChoices)
            continue
        
        option.get(cmd, NullFunc)(session, connection)
        input("Press any key to continue...")

    session.close()
    connection.close()
    print("\r[+]\tDone...")