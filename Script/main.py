import mysql.connector as sql
from mysql.connector import errorcode
import random
from faker import Faker

VERBAL = False
dbName = "GameData"

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
        session.execute("CREATE DATABASE {} DEFAULT CHARACTER SET 'utf8'".format(dbName))
    except sql.Error as err:
        print("\r[{}]\tFailed to create database '{}' with error: '{}'".format("w" if err.errno == 1007 else "-", dbName, err))
        retCode = -1
    return retCode

def _UseDatabase(session):
    retCode = 0
    try:
        session.execute("USE {};".format(dbName))
    except sql.Error as err:
        print("\r[w]\tFailed to set database with error: '{}'.".format(err))
        retCode = -1
    return retCode

def _InitTables(session):
    queries = [
        "CREATE TABLE Accounts ("               \
            "Id INT NOT NULL AUTO_INCREMENT,"   \
            "Username varchar(255) NOT NULL,"   \
            "Password varchar(255) NOT NULL,"   \
            "FirstName varchar(255) NOT NULL,"  \
            "LastName varchar(255) NOT NULL,"   \
            "Active boolean NOT NULL,"          \
            "PRIMARY KEY (Id)"                  \
        ");",
        
        "CREATE TABLE Servers ("            \
            "Name VARCHAR(255) NOT NULL,"   \
            "Capacity INT NOT NULL,"        \
            "ActivePlayers INT NOT NULL,"   \
            "Status VARCHAR(255) NOT NULL," \
            "PRIMARY KEY (Name)"            \
        ");",
        
        # Guilds here are cross-server and hence are only limited by name
        "CREATE TABLE Guilds ("                                 \
            "Name VARCHAR(255) NOT NULL,"                       \
            "Members INT NOT NULL,"                             \
            "Score INT NOT NULL,"                               \
            "Active Boolean NOT NULL,"                          \
            "PRIMARY KEY (Name)"                                \
        ");",
        
        # PC here uses a "Composite Key" to let names be server bound
        "CREATE TABLE PlayerCharacters ("                           \
            "Name varchar(255) NOT NULL,"                           \
            "AccountId INT NOT NULL,"                               \
            "ServerId VARCHAR(255) NOT NULL,"                       \
            "GuildId VARCHAR(255),"                                 \
            "IsLoggedIn Boolean NOT NULL,"                            \
            "Level INT NOT NULL,"                                   \
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
        "END"
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
        session.execute("DROP DATABASE {}".format(dbName))
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
    print("\r[{}]".format("-"*50),end="")
    print("\r[", end="", flush=True)
    
    
    # Fake data generator
    fData = Faker()
    
    numServers = random.randint(2, 10)
    serverNames = [fData.unique.country() for i in range(numServers * 15)]
    for i, name in enumerate(serverNames):
        if _SafeQuery( 
            session,
            "INSERT INTO Servers VALUES (\"{}\", {}, 0, \"Running\");".format(name, random.randint(100, 1000))
            ) != 0:
            return -1
        connection.commit()
        if i % numServers == 0:
            print("{}".format("x"), end="", flush=True)
    
    numGuilds = random.randint(2, 20)
    guildNames = [fData.unique.city() for i in range(numGuilds * 15)]
    for i, name in enumerate(guildNames):
        if _SafeQuery( 
            session,
            "INSERT INTO Guilds VALUES (\"{}\", 0, {}, True);".format(name, random.randint(100,10_000))
            ) != 0:
            return -1
        connection.commit()
        if (i % numGuilds == 0):
            print("{}".format("x"), end="", flush=True)
    
    numAccounts = random.randint(25, 500)
    for i in range(numAccounts * 20):
        if _SafeQuery(
            session,
            "INSERT INTO Accounts VALUES (0, \"{}\", \"{}\", \"{}\", \"{}\", True);".format(
                fData.street_name(),
                fData.password(),
                fData.first_name(),
                fData.last_name()
            )) != 0:
            return -1
        connection.commit()

        numCharacters = random.randint(1, 12)
        for _ in range(numCharacters):
            while _SafeQuery(
                session,
                "INSERT INTO PlayerCharacters VALUES (\"{}\", {}, \"{}\", \"{}\", {}, {}, \"{}\");".format(
                    fData.name(), # Character name
                    i + 1, # Account id
                    random.choice(serverNames), # Server
                    random.choice(guildNames), # Guild
                    fData.boolean(), # Logged in
                    random.randint(1, 20), # Level
                    random.choice([  # Class
                            "Fighter",
                            "Cleric",
                            "Ranger",
                            "Wizard",
                            "Sorcerer",
                            "Warlock",
                            "Bard",
                            "Barbarian",
                            "Druid"
                        ])
                ),
                silent=True
                ) != 0:
                pass
            connection.commit()
        
        if (i % numAccounts == 0):
            print("{}".format("x"), end="", flush=True)
    print("\r\n[+]\tFinished generating data...", flush=True)
    return 0

def RePopulateTables(session, connection):
    if DeleteDB(session) != 0:
        return -1
    if CreateDB(session) != 0:
        return -1
    return PopulateTables(session, connection)
# ================================================== ==================================================

def NullFunc(*void):
    return
def PrintHelp(*void):
    print("Options:\n0: Quit\n1: Create Database\n2: Delete Database\n3: Generate Table Data\n4: Re-Generate Table Data\n5: Help")

if __name__ == "__main__":
    connection = SQLConnect()
    session = connection.cursor()
    
    switchCase = {
        # Option "1: Init Database"
        1: CreateDB,
        # Option "2: Delete Database"
        2: DeleteDB,
        # Option "3: Generate Data"
        3: PopulateTables,
        # Option "4: Re-Generate Data"
        4: RePopulateTables,
        5: PrintHelp
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