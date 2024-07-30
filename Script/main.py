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
 
def _SafeQuery(session, query):
    retCode = 0
    try:
        session.execute(query)
    except sql.Error as err:
        print("\r[w]\tQuery '{}' failed with error: '{}'".format(query, session))
        retCode = -1
    return retCode

def CreateDB(session):    
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

def DeleteDB(session):
    retCode = 0
    try:
        session.execute("DROP DATABASE {}".format(dbName))
        print("\r[+]\tDeleted Database")
    except sql.Error as err:
        print("\r[w]\tCould not delete database, error: '{}'".format(err))
        retCode = -1
    return retCode 

def PopulateTables(session):
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
    print("\r[", end="")
    
    
    # Fake data generator
    fData = Faker()
    
    numServers = random.randint(10, 15)
    # Generate ...
    print("{}".format("x"*15), end="")
    
    
    numGuilds = random.randint(1, 5_000)
    # Generate ...
    print("{}".format("x"*15), end="")
    
    
    numAccounts = random.randint(100, 10_000)
    accounts = []
    #for uid in range(2):
    #    print(fData.first_name())
    #    print(fData.last_name())
    #    print(uid)
    #    print(fData.password())
    
    for i in range(numAccounts):
        numCharacters = random.randint(1, 12)
        numItems = random.randint(1, 128)
        # Generate ...
        
    print("{}".format("x"*20))
    print("\r\n[+]\tFinished generating data...")
    return 0

def RePopulateTables(session):
    if DeleteDB(session) != 0:
        return -1
    if CreateDB(session) != 0:
        return -1
    return PopulateTables(session)
# ================================================== ==================================================

def PrintHelp(void):
    print("Options:\n0: Quit\n1: Create Database\n2: Delete Database\n3: Generate Table Data\n4: Re-Generate Table Data\n5: Help")
def NullFunc(void):
    return

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
    
    PrintHelp(0)
    while True:
        cmd = int(input("Enter input: "))
        if cmd == 0:
            break
        
        switchCase.get(cmd, NullFunc)(session)
    
    
    session.close()
    connection.close()
    print("\r[+]\tDone...")