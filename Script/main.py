import mysql.connector as sql
from mysql.connector import errorcode


#For this project I want to create a database back-end for a game. Meaning that the database will track every player, their associated server (and the servers themselves). It will also keep track of every players inventory.
#The reasoning for these two things is that the inventory can be easily rolled back in case something happens, and it will be easy for players to query items they have.
#As for the servers, this will allow players to have a friends list or similar functionality and thereby quickly and efficiently query for all of the player data of their friends (to then be displayed by the game).
#The meta data used by the server can for example be a number for amount of players who play on it, and however many are online. This can easily be updated by a trigger instead of having to query the entire server every time this data gets requested.
#The amount of things stored in this data set can easily be expanded to cover more things such as, friends, team members, guild members, etc.


def SQLConnect():
    return sql.connect(
        user='Dan',
        password='admin',
        # database='GameData',
        # host='127.0.0.1:3306'
        unix_socket= '/Applications/MAMP/tmp/mysql/mysql.sock'
    )


def InitDatabase(session, dbName):
    try:
        session.execute("CREATE DATABASE {} DEFAULT CHARACTER SET 'utf8'".format(dbName))
    except sql.Error as err:
        print("Failed to create database '{}' with error '{}'".format(dbName, err))
        if err.errno != 1007:
            exit(1)


def InitTables(session):
    query = "" \
            ""
    
    try:
        session.execute(query)
    except sql.Error as err:
        print("Failed to create tables with error '{}'".format(err))
        if err.errno != 1007:
            exit(1)

            
def PopulateTables(session):
    return


if __name__ == "__main__":
    connection = SQLConnect()
    session = connection.cursor()
    
    
    InitDatabase(session, "GameData")
    InitTables(session)
    
    
    session.execute("DROP DATABASE GameData")
    
    session.close()
    connection.close()
    print("Done...")