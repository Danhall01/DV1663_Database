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

g_classes = [
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
        if CreateGuild(session, connection, name, silent=True) != 0:
            return -1
        if (i % numGuilds == 0):
            print("{}".format(g_LoadbarCharacter), end="", flush=True)
    
    # Insert Admin Account
    if CreateAccount(session, connection, "Admin", "Root", "Daniel", "Häll", silent=True) != 0:
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
            silent=True
        )
        if not fData.boolean():
            SetUserStatus(session, connection, uid, False, silent=True)

        numCharacters = random.randint(1, MAX_CHARACTERS)
        for _ in range(numCharacters):
            while True:
                nameChoice = fData.name()
                serverChoice = random.choice(serverNames)
                if CreateCharacter(session, connection,
                                  uid,
                                  nameChoice,
                                  serverChoice,
                                  random.choice(g_classes),
                                  silent=True) != 0:
                    continue
                if LevelUp(session,connection, uid, nameChoice, serverChoice, random.randint(0, 19), silent=True) != 0:
                    return -1
                
                # Return values here are only relevant to UI
                if fData.boolean():
                    LogInCharacter(session, connection, uid, nameChoice, serverChoice, silent=True)
                if fData.boolean():
                    JoinGuild(session, connection, uid, nameChoice, serverChoice, random.choice(guildNames), silent=True)
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
def LogInAccount(session, void, userId=None, userName=None, password=None, silent=False):
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
    while username == None or password == None or firstName == None or lastName == None:
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

def CreateCharacter(session, connection, userId=None, characterName=None, server=None, className=None, silent=False):
    if userId == None:
        global g_activeUser
        if not g_activeUser:
            if not silent:
                print("\r[w]\tUnable to create characters, you are not logged in")
                return -1
        userId = g_activeUser[0]
    if characterName == None:
        characterName = GetInput_s("Enter Character name: ")
    if server == None:
        server = GetInput_s("Enter server name: ")
    if className == None:
        global g_classes
        for i, c in enumerate(g_classes):
            print("{}: {}".format(i,c))
        className = g_classes[GetInput_s("Which class would you like to create?: ", lambda arg: int(arg) if int(arg) < len(g_classes) and int(arg) >= 0 else None)]
    
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
        if not silent:
            print("\r[w]\tCould not create character \"{}-{}\"".format(characterName, server))
        return -1
    connection.commit()
    if not silent:
        print("\r[+]\tSuccessfully created character \"{}-{}\"".format(characterName, server))
    return 0

def DeleteCharacter(session, connection, userId=None, characterName=None, server=None, silent=False):
    if userId == None:
        global g_activeUser
        if not g_activeUser:
            if not silent:
                print("\r[w]\tUnable to create characters, you are not logged in")
                return -1
        userId = g_activeUser[0]
    
    if characterName == None:
        characterName = GetInput_s("Enter Character Name: ")
    if server == None:
        server = GetInput_s("Enter Server Name: ")
    
    queryLookUp = "SELECT * FROM PlayerCharacters "\
        "WHERE PlayerCharacters.Name = \"{}\" "\
        "AND PlayerCharacters.ServerId = \"{}\" "\
        "AND PlayerCharacters.AccountId = {};"\
        "".format(characterName, server, userId)
    if _SafeQuery(session, queryLookUp) != 0:
        return -1
    found = session.fetchall()
    if len(found) != 1:
        if not silent:
            print("\r[w]\tNo such character found, ensure you are logged in to the right account")
        return -1
    
    # In case character is deleted while online? (Why)
    queryLogout = "UPDATE PlayerCharacters SET PlayerCharacters.IsLoggedIn = False "\
        "WHERE PlayerCharacters.Name = \"{}\" "\
        "AND PlayerCharacters.ServerId = \"{}\" "\
        "AND PlayerCharacters.AccountId = {};"\
        "".format(characterName, server, userId)
    if _SafeQuery(session, queryLogout) != 0:
        return -1
    connection.commit()
    
    query = "DELETE FROM PlayerCharacters "\
        "WHERE PlayerCharacters.Name = \"{}\" "\
        "AND PlayerCharacters.ServerId = \"{}\" "\
        "AND PlayerCharacters.AccountId = {};"\
        "".format(characterName, server, userId)
    if _SafeQuery(session, query) != 0:
        return -1
    connection.commit()
    
    if not silent:
        print("\r[+]\tSuccessfully deleted character {}-{}".format(characterName, server))

def LogInCharacter(session, connection, userId=None, characterName=None, server=None, silent=False):
    if userId == None:
        global g_activeUser
        if not g_activeUser:
            if not silent:
                print("\r[w]\tUnable to create characters, you are not logged in")
                return -1
        userId = g_activeUser[0]
    if characterName == None:
        characterName = GetInput_s("Enter Character name: ")
    if server == None:
        server = GetInput_s("Enter server name: ")
    
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
    if not silent:
        print("\r[+]\tSuccessfuly logged in character \"{}-{}\" to server \"{}\"".format(characterName, server, server))
    return 0

def DisplayAllCharactersAccount(session, void, userId=None, silent=False):
    if userId == None:
        global g_activeUser
        if not g_activeUser:
            print("\r[w]\tUnable to list characters, you are not logged in")
            return -1
        userId = g_activeUser[0]
    
    queryAccount = "SELECT a.Username, a.Id, a.FirstName, a.LastName, a.Active FROM Accounts a WHERE a.Id = {};"\
        "".format(userId)
    if _SafeQuery(session, queryAccount) != 0:
        return -1
    user = session.fetchall()
    if len(user) == 0:
        print("\r[w]\tCould not find account")
        return -1
    user = user[0]
    
    print("\033[H\033[J", end="")
    print("\r{}#{} ({})\n\r({} {})\n".format(user[0], user[1], "Active" if user[4] else "Inactive", user[2], user[3]))
    
    query = "SELECT p.Name, p.Class, p.Level, p.IsLoggedIn, "\
                "s.Name as serverName, s.Status, "\
                "g.Name as guildName, g.Score, g.Members, ( "\
                    "SELECT COUNT(*) FROM PlayerCharacters p2 WHERE p2.GuildId = g.Name AND p2.IsLoggedIn = True "\
                ") as OnlineMembers "\
                "FROM playercharacters p "\
            "LEFT JOIN Guilds g ON g.Name = p.GuildId "\
            "INNER JOIN servers s ON s.Name = p.ServerId "\
            "WHERE p.AccountId = {} "\
            "ORDER BY p.Level DESC; "\
            "".format(userId)
    if _SafeQuery(session, query) != 0:
        return -1
    blob = session.fetchall()
    if len(blob) == 0:
        print("\r[w]\tCould not find any characters on account")
        return -1
    print("Characters: {}/{}".format(len(blob), str(MAX_CHARACTERS)))
    
    padName = max(max(len("\"" + character[0] + "\"" + "-" + character[4]), len(character[1])) for character in blob)
    padStatus = max(max(len(character[5]) + 1 for character in blob), len("Lvl: 20"))
    for characterblob in blob:
        (cName, className, Level, isLoggedIn, 
         serverName, serverStatus, guildName, 
         guildScore, guildMembers, guildMembersOnline) = characterblob
        
        formatName = "\"" + cName + "\"" + "-" + serverName
        formatClassName = "\t" + className
        formatLevel = "Lvl: " + str(Level)
        formatStatus = "(" + serverStatus + ")"
        formatGuildData = "{}({}/{}, {})".format(guildName, guildMembersOnline, guildMembers, guildScore)
        
        print("\r{} {} | {}"\
              "".format(formatName.ljust(padName + 1),
                        formatStatus.ljust(padStatus + 1),
                        formatGuildData if guildName else "No Guild"))
        print("\r{}{} | {}\n"\
            "".format(formatClassName.ljust(padName - 4),
                      formatLevel.ljust(padStatus),
                      "Online" if isLoggedIn else ""))

    if not silent:
        print("\r[+]\tFinished listing characters")
    return 0

def LevelUp(session, connection, userId=None, characterName=None, server=None, levels=None, silent=False):
    if userId == None:
        global g_activeUser
        if not g_activeUser:
            if not silent:
                print("\r[w]\tUnable to create characters, you are not logged in")
                return -1
        userId = g_activeUser[0]
    if characterName == None:
        characterName = GetInput_s("Enter Character name: ")
    if server == None:
        server = GetInput_s("Enter Server name: ")
    if levels == None:
        levels = GetInput_s("Enter amount of levels to give character (int, 1-20): ", lambda arg: arg if arg <=20 and arg > 0 else None)
    
    query = "UPDATE PlayerCharacters " \
            "SET PlayerCharacters.Level = LEAST(PlayerCharacters.Level + GREATEST(0, {}), 20) "\
            "WHERE PlayerCharacters.Name = \"{}\" AND PlayerCharacters.ServerId = \"{}\" AND PlayerCharacters.AccountId = {};"\
            "".format(
                    levels,
                    characterName,
                    server,
                    userId)
    if _SafeQuery(session, query) != 0:
        return -1
    connection.commit()
    
    queryLookupLevel = "SELECT level FROM PlayerCharacters WHERE PlayerCharacters.Name = \"{}\" AND PlayerCharacters.Server = \"{}\";"
    
    if not silent:
        print("\t[+]\tSuccessfully leveled up character \"{}-{}\" to level {}")
    return 0

def JoinGuild(session, connection, userId=None, characterName=None, server=None, guildName=None, silent=False):
    if userId == None:
        global g_activeUser
        if not g_activeUser:
            if not silent:
                print("\r[w]\tUnable to create characters, you are not logged in")
                return -1
        userId = g_activeUser[0]
    if characterName == None:
        characterName = GetInput_s("Enter Character name: ")
    if server == None:
        server = GetInput_s("Enter Server name: ")
    if guildName == None:
        guildName = GetInput_s("Enter Guild name: ")
    
    query = "UPDATE PlayerCharacters " \
            "SET PlayerCharacters.GuildId = \"{}\" "    \
            "WHERE PlayerCharacters.Name = \"{}\" "     \
            "AND PlayerCharacters.ServerId = \"{}\" "   \
            "AND PlayerCharacters.AccountId = {};"   \
            "".format(guildName, characterName, server, userId)
            
    if _SafeQuery(session, query) != 0:
        return -1
    connection.commit()
    if not silent:
        print("\r[+]\t\"{}-{}\" succsessfully joined the guild \"{}\"".format(characterName, server, guildName))
    return 0

def LeaveGuild(session, connection, userId=None, characterName=None, server=None, silent=False):
    if userId == None:
        global g_activeUser
        if not g_activeUser:
            if not silent:
                print("\r[w]\tUnable to create characters, you are not logged in")
                return -1
        userId = g_activeUser[0]
    if characterName == None:
        characterName = GetInput_s("Enter Character name: ")
    if server == None:
        server = GetInput_s("Enter Server name: ")
    
    query = "UPDATE PlayerCharacters " \
            "SET PlayerCharacters.GuildId = NULL "    \
            "WHERE PlayerCharacters.Name = \"{}\" "     \
            "AND PlayerCharacters.ServerId = \"{}\" "   \
            "AND PlayerCharacters.AccountId = {};"   \
            "".format(characterName, server, userId)
            
    if _SafeQuery(session, query) != 0:
        return -1
    connection.commit()
    if not silent:
        print("\r[+]\t\"{}-{}\" Succsessfully left their guild".format(characterName, server))
    return 0

def ListGuilds(session, *void):
    query = "SELECT Name, Members, Score FROM Guilds;"
    if _SafeQuery(session, query) != 0:
        return -1
    data = session.fetchall()
    
    maxlenName = max(len(guild[0]) for guild in data)
    stop = 1
    for i, guild in enumerate(data):
        print("\r{}: {}\tMembers: {}\tScore {}"\
            "".format(i, str(guild[0]).ljust(maxlenName + 1), str(guild[1]).ljust(5), guild[2]))
        if i != 0 and i % 5 == 0:
            stop = input("\rPress enter to continue or 0 to stop: ")
        try:
            stop = int(stop)
        except:
            continue
        if stop == 0:
            break
    return 0

def SearchGuild(session, void, guildName=None):
    if guildName == None:
        guildName = GetInput_s("Enter Guildname: ")
    
    query = "SELECT Name, Members, Score FROM Guilds WHERE Guilds.Name = \"{}\";".format(guildName)
    if _SafeQuery(session, query) != 0:
        return -1
    data = session.fetchall()
    if len(data) == 0:
        print("\r[w]\tCould not find guild \"{}\", ensure the name was spelt correctly")
        return -1
    
    guild = data[0]
    maxlenName = len(guild[0])
    print("\r1: {}\tMembers: {}\tScore {}"\
            "".format(str(guild[0]).ljust(maxlenName + 1), str(guild[1]).ljust(5), guild[2]))
    return 0

def ReserveGuildName(session, connection, guildName=None, silent=False):
    if guildName == None:
        guildName = GetInput_s("Enter Guildname: ")
    
    queryExists = "SELECT * FROM Guilds WHERE Guilds.Name = \"{}\";"\
        "".format(guildName)
    if _SafeQuery(session, queryExists) != 0:
        return -1
    result = session.fetchall()
    if len(result) == 0: # Guild does not exist
        print("\r[w]\tGuild did not already exist, creating...")
        CreateGuild(session, connection, guildName)
        
    queryReserve = "UPDATE Guilds SET Guilds.Active = True WHERE Guilds.Name = \"{}\";"\
        "".format(guildName)
    if _SafeQuery(session, queryReserve) != 0:
        return -1
    connection.commit()
    if not silent:
        print("\r[+]\tSuccessfully reserved guild \"{}\"".format(guildName))
    return 0

def CreateGuild(session, connection, guildName=None, silent=False):
    if guildName == None:
        guildName = GetInput_s("Enter Guildname: ")
    
    query = "INSERT INTO Guilds VALUES (\"{}\", 0, 0, False);"\
        "".format(guildName)
    if _SafeQuery(session, query) != 0:
        return -1
    connection.commit()
    if not silent:
        print("\r[+]\tSuccessfully created guild \"{}\"".format(guildName))
    return 0


def ListGuildMembers(session, void, guildName=None, silent=False):
    if guildName == None:
        guildName = GetInput_s("Enter Guildname: ")
    
    query = "SELECT p.Name, p.Class, p.Level, p.IsLoggedIn, "\
                "s.Name as serverName, s.Status, "\
                "g.Name as guildName, g.Score, g.Members, ( "\
                    "SELECT COUNT(*) FROM PlayerCharacters p2 WHERE p2.GuildId = g.Name AND p2.IsLoggedIn = True "\
                ") as OnlineMembers "\
                "FROM playercharacters p "\
            "LEFT JOIN Guilds g ON g.Name = p.GuildId "\
            "INNER JOIN servers s ON s.Name = p.ServerId "\
            "WHERE p.GuildId = \"{}\" AND p.IsLoggedIn = True "\
            "ORDER BY p.Level DESC; "\
            "".format(guildName)
    if _SafeQuery(session, query) != 0:
        return -1
    blob = session.fetchall()
    if len(blob) == 0:
        print("\r[w]\tNo players currently playing in guild (Or guild does not exist)")
        return -1
    print("Currently online characters in \"{}\": {}/{}".format(guildName, len(blob), str(blob[0][8])))
    
    padName = max(max(len("\"" + character[0] + "\"" + "-" + character[4]), len(character[1])) for character in blob)
    padStatus = max(max(len(character[5]) + 1 for character in blob), len("Lvl: 20"))
    for characterblob in blob:
        (cName, className, Level, isLoggedIn, 
         serverName, serverStatus, guildName, 
         guildScore, guildMembers, guildMembersOnline) = characterblob
        
        formatName = "\"" + cName + "\"" + "-" + serverName
        formatClassName = "\t" + className
        formatLevel = "Lvl: " + str(Level)
        formatStatus = "(" + serverStatus + ")"
        formatGuildData = "{}({}/{}, {})".format(guildName, guildMembersOnline, guildMembers, guildScore)
        
        print("\r{} {} | {}"\
              "".format(formatName.ljust(padName + 1),
                        formatStatus.ljust(padStatus + 1),
                        formatGuildData if guildName else "No Guild"))
        print("\r{}{} | {}\n"\
            "".format(formatClassName.ljust(padName - 4),
                      formatLevel.ljust(padStatus),
                      "Online" if isLoggedIn else ""))

    if not silent:
        print("\r[+]\tFinished listing characters")
    return 0

#TODO
# Get Top Guild Information (Players JOIN Guild JOIN Server(guild[Low]:\nPlayers...))
def ListTopGuild(session, *void):
    pass

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
        queryExists = "SELECT * FROM Guilds WHERE Guilds.Name = \"{}\";".format(guildName)
        if _SafeQuery(session, queryExists) != 0:
            return -1
        if len(session.fetchall()) != 1:
            print("\r[w]\tNo guild named \"{}\" exists".format(guildName))
            return -1
        
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
        "3: Display all Characters on Account\n"\
        "4: Create Character\n"\
        "5: Delete Character\n"\
        "6: Login to Character\n"\
        "7: Level up Character\n"\
        "8: Join Guild\n"\
        "9: Leave Guild\n"\
            "\n"\
        "10: List all Guilds\n"\
        "11: Search for Guild\n"\
        "12: Reserve Guild Name\n"\
        "13: Create Guild\n"\
        "14: List all Guild Members (Specific guild)\n"\
        "15: List Top Guild Members\n"
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
        
        3: DisplayAllCharactersAccount,
        4: CreateCharacter,
        5: DeleteCharacter,
        6: LogInCharacter,
        7: LevelUp,
        8: JoinGuild,
        9: LeaveGuild,
        
        10: ListGuilds,
        11: SearchGuild,
        12: ReserveGuildName,
        13: CreateGuild,
        14: ListGuildMembers,
        15: ListTopGuild,
        
        16: UserHelp
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