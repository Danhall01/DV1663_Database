import mysql.connector as sql
from mysql.connector import errorcode
import random
from faker import Faker

#TODO Systems:
# Inventory system
# Friends system

#TODO Anything interesting to look at from program:
# Set Active account (Program)
# Activate / Deactivate Account
# Create / Delete Characters
# Make server go down / into maintinance or go up again (Admin Account)
# Reserve Guildname (Set active with no members)
# Collect items (GetRandomItem())

VERBAL = False
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
    retCode = 0
    try:
        session.execute(query)
    except sql.Error as err:
        if not silent:
            print("\r[w]\tQuery '{}' failed with error: '{}'".format(query, session))
        retCode = -1
    return retCode

def CreateServer(session, connection, name, capacity=256):
    query = "INSERT INTO Servers VALUES (\"{}\", {}, 0, \"Inactive\");"\
        "".format(name, capacity)
    if _SafeQuery(session, query) != 0:
        return -1
    connection.commit()
    return 0

def CreateGuild(session, connection, name):
    query = "INSERT INTO Guilds VALUES (\"{}\", 0, 0, False);"\
        "".format(name)
    if _SafeQuery(session, query) != 0:
        return -1
    connection.commit()
    return 0

def CreateUser(session, connection, username, password, fName, lName):
    query = "INSERT INTO Accounts VALUES (0, \"{}\", \"{}\", \"{}\", \"{}\", True);"\
        "".format(
                username,
                password,
                fName,
                lName,
            )
    if _SafeQuery(session, query) != 0:
        return -1
    connection.commit()
    return 0

def CreateCharacter(session, connection, name, whom, server, className):
    query = "INSERT INTO PlayerCharacters VALUES (\"{}\", {}, \"{}\", {}, {}, {}, \"{}\");"\
        "".format(
                name,       # Character name
                whom,       # Account id
                server,     # Server
                "NULL",     # Guild
                False,      # Logged in
                1,          # Level
                className   # Class
                )
    if _SafeQuery(session, query, silent=True) != 0:
        return -1
    connection.commit()
    return 0

def LogInCharacter(session, connection, userId, name, server, silent=False):
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

    queryServerCapacity = "SELECT Servers.Capacity, Servers.ActivePlayers "\
                          "FROM Servers "\
                          "WHERE Servers.Name = \"{}\";"\
                          "".format(server)
    if _SafeQuery(session, queryServerCapacity) != 0:
        return -1
    capacity, players = session.fetchall()[0]
    if players + 1 > capacity:
        if not silent:
            print("\r[w]\tCould not log in, server \"{}\" is currently full".format(server))
        return -1
    
    # Log In
    queryLogIn = "UPDATE PlayerCharacters "\
                "SET PlayerCharacters.IsLoggedIn = True "\
                "WHERE PlayerCharacters.Name = \"{}\" "\
                "AND PlayerCharacters.ServerId = \"{}\""\
                "".format(name, server)
    if _SafeQuery(session, queryLogIn) != 0:
        return -1
    connection.commit()
    return 0

def LevelUp(session, connection, name, server, levels):
    query = "UPDATE PlayerCharacters " \
            "SET PlayerCharacters.Level = LEAST(PlayerCharacters.Level + GREATEST(0, {}), 20) "\
            "WHERE PlayerCharacters.Name = \"{}\" AND PlayerCharacters.ServerId = \"{}\";"\
            "".format(
                    levels,
                    name,
                    server)
    if _SafeQuery(session, query) != 0:
        return -1
    connection.commit()
    return 0

def DisableUser(session, connection, userId):
    query = "UPDATE Accounts SET Accounts.Active = False WHERE Accounts.Id = {}".format(userId)
    if _SafeQuery(session, query)!= 0:
        return -1
    connection.commit()
    return 0

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
        if CreateServer(session, connection, name, random.randint(64, 256)) != 0:
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
    if CreateUser(session, connection, "Admin", "Root", "Daniel", "Häll") != 0:
        return -1
    
    numAccounts = random.randint(25, 150)
    for i in range(numAccounts * 20):
        active = fData.boolean()
        CreateUser(session, connection,
            fData.street_name(),
            fData.password(),
            fData.first_name(),
            fData.last_name(),
        )
        if not active:
            DisableUser(session, connection, i + 1)

        numCharacters = random.randint(1, 12)
        for _ in range(numCharacters):
            while True:
                nameChoice = fData.name()
                serverChoice = random.choice(serverNames)
                if CreateCharacter(session, connection,
                                  nameChoice, 
                                  i + 1, 
                                  serverChoice, 
                                  random.choice(g_Classes)) != 0:
                    continue
                if LevelUp(session,connection, nameChoice, serverChoice, random.randint(0, 19)) != 0:
                    return -1
                if fData.boolean():
                    # Log in or not, it does not really matter here
                    LogInCharacter(session, connection, i + 1, nameChoice, serverChoice, silent=True)
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

def NullFunc(*void):
    return
def PrintHelp(*void):
    print(
        "Options:\n"                  \
        "0: Quit\n"                   \
        "1: Create Database\n"        \
        "2: Delete Database\n"        \
        "3: Recreate Database\n"      \
        "4: Generate Table Data\n"    \
        "5: Re-Generate Table Data\n" \
        "6: Help"
    )


if __name__ == "__main__":
    connection = SQLConnect()
    session = connection.cursor()
    
    switchCase = {
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
        6: PrintHelp
    }
    
    PrintHelp()
    while True:
        try:
            cmd = int(input("Enter input: "))
        except:
            print("\r[w]\tInvalid Input, try again...")
            continue
        if cmd == 0:
            break
        
        switchCase.get(cmd, NullFunc)(session, connection)

    session.close()
    connection.close()
    print("\r[+]\tDone...")