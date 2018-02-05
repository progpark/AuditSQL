# -*- coding:utf-8 -*-
# edit by fuzongfei

import pymysql

from AuditSQL import settings
from ProjectManager.models import InceptionHostConfig


class InceptionApi(object):
    def __init__(self):
        try:
            self.inception_host = getattr(settings, 'INCEPTION_HOST')
            self.inception_port = int(getattr(settings, 'INCEPTION_PORT'))
        except Exception as err:
            raise ValueError(err)

    def sqlprepare(self, sqlcontent, host, database, action='check'):
        master = InceptionHostConfig.objects.get(host=host)
        masterHost = master.host
        masterUser = master.user
        masterPassword = master.password
        masterPort = master.port
        masterDatabase = database

        # 连接到目标数据库，进行数据分析操作
        if action == 'check':
            sqlJoin = f"/*--user={masterUser};--password={masterPassword};--host={masterHost};--enable-check=1;--port={masterPort};*/" \
                      f"\ninception_magic_start;" \
                      f"\nuse {masterDatabase};" \
                      f"\n{sqlcontent}" \
                      f"\ninception_magic_commit;"
        if action == 'execute':
            sqlJoin = f"/*--user={masterUser};--password={masterPassword};--host={masterHost};--execute=1;--port={masterPort};*/" \
                      f"\ninception_magic_start;" \
                      f"\nuse {masterDatabase};" \
                      f"\n{sqlcontent}" \
                      f"\ninception_magic_commit;"

        try:
            # 连接到inception
            conn = pymysql.connect(host=f"{self.inception_host}", user='root', password='', db='',
                                   port=self.inception_port, use_unicode=True, charset="utf8")
            cur = conn.cursor()
            cur.execute(sqlJoin)
            result = cur.fetchall()
            field_names = [i[0] for i in cur.description]
            result_all = []
            for row in result:
                result_all.append(dict(map(lambda x, y: [x, y], field_names, row)))
            cur.close()
            conn.close()
            return result_all
        except pymysql.Error as e:
            print("Mysql Error %d: %s" % (e.args[0], e.args[1]))


class GetBackupApi(object):
    """从备份主机上获取备份数据"""

    def __init__(self, sequence_result):
        self.inception_backup_host = getattr(settings, 'INCEPTION_BACKUP_HOST')
        self.inception_backup_user = getattr(settings, 'INCEPTION_BACKUP_USER')
        self.inception_backup_password = getattr(settings, 'INCEPTION_BACKUP_PASSWORD')
        self.inception_backup_port = getattr(settings, 'INCEPTION_BACKUP_PORT')

        self.sequence_result = sequence_result

    def get_backupinfo(self):
        conn = pymysql.connect(host=self.inception_backup_host, user=self.inception_backup_user,
                               password=self.inception_backup_password,
                               port=self.inception_backup_port, use_unicode=True, charset="utf8")
        cur = conn.cursor()

        rollbackResult = []
        for row in self.sequence_result:
            # 如果备份的库记录为空，跳过
            if row['backupdbName'] != 'None':
                dstTableQuery = f"select tablename from {row['backupdbName']}.$_$inception_backup_information$_$ where opid_time='{row['sequence']}'"
                cur.execute(dstTableQuery)
                dstTable = cur.fetchone()[0]

                rollbackStatementQuery = f"select group_concat(rollback_statement separator '\n') from {row['backupdbName']}.{dstTable} where opid_time='{row['sequence']}' group by opid_time"
                cur.execute(rollbackStatementQuery)

                for i in cur.fetchall():
                    rollbackResult.append(i[0])
        cur.close()
        conn.close()
        return '\n'.join(rollbackResult)


class GetDatabaseApi(object):
    """获取目标主机的所有库"""

    def __init__(self, host):
        self.host = host

    IGNORED_PARAMS = ['information_schema', 'mysql', 'percona']

    def get_dbname(self):
        master = InceptionHostConfig.objects.get(host=self.host)
        masterHost = master.host
        masterUser = master.user
        masterPassword = master.password
        masterPort = master.port

        conn = pymysql.connect(host=masterHost, user=masterUser,
                               password=masterPassword,
                               port=masterPort, use_unicode=True, charset="utf8")
        cur = conn.cursor()
        dbQuery = "select schema_name from information_schema.schemata"
        cur.execute(dbQuery)
        dbResult = []
        for i in cur.fetchall():
            dbResult.append(i[0])

        for i in self.IGNORED_PARAMS:
            if i in dbResult:
                dbResult.remove(i)

        cur.close()
        conn.close()

        return dbResult