import sqlite3

# TOOD: add logging
# TODO: escape sql ??


class SQLiteBackend:

    def __init__(self, dbname="if.sqlite"):
        self.dbname = dbname
        self.conn = sqlite3.connect(dbname)

    def setup(self):
        tblstmt = "CREATE TABLE IF NOT EXISTS items (starttime integer, owner text)"
        itemidx = "CREATE INDEX IF NOT EXISTS itemIndex ON items (starttime ASC)"
        ownidx = "CREATE INDEX IF NOT EXISTS ownIndex ON items (owner ASC)"
        self.conn.execute(tblstmt)
        self.conn.execute(itemidx)
        self.conn.execute(ownidx)
        self.conn.commit()

    def add(self, starttime, owner):
        stmt = "INSERT INTO items (starttime, owner) VALUES (?, ?)"
        args = (starttime, owner)
        self.conn.execute(stmt, args)
        self.conn.commit()

    def delete(self, owner):
        stmt = "DELETE FROM items WHERE owner = (?)"
        self.conn.execute(stmt, (owner,))
        self.conn.commit()

    def get(self, owner):
        stmt = "SELECT starttime, owner FROM items WHERE owner = (?)"
        args = (owner, )
        try:
            return [x for x in self.conn.execute(stmt, args)][0]
        except IndexError:
            return None

    def all(self):
        stmt = "SELECT * FROM items"
        return [x for x in self.conn.execute(stmt)]


def db(backend='SQLiteBackend'):
    return globals.get(backend)()
