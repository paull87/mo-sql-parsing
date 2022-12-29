# encoding: utf-8
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.
#
# Author: Kyle Lahnakoski (kyle@lahnakoski.com)
#

from __future__ import absolute_import, division, unicode_literals

from unittest import TestCase

from mo_parsing.debug import Debugger

from mo_sql_parsing import parse


class TestPostgres(TestCase):
    def test_issue_15(self):
        sql = """
        SELECT 
            id, 
            create_date AT TIME ZONE 'UTC' as created_at, 
            write_date AT TIME ZONE 'UTC' as updated_at
        FROM sometable;
        """
        result = parse(sql)

        self.assertEqual(
            result,
            {
                "from": "sometable",
                "select": [
                    {"value": "id"},
                    {
                        "name": "created_at",
                        "value": {"": ["create_date", {"literal": "UTC"}]},
                    },
                    {
                        "name": "updated_at",
                        "value": {"": ["write_date", {"literal": "UTC"}]},
                    },
                ],
            },
        )

    def test_issue_20a(self):
        sql = """SELECT Status FROM city WHERE Population > 1500 INTERSECT SELECT Status FROM city WHERE Population < 500"""
        result = parse(sql)
        expected = {"intersect": [
            {
                "from": "city",
                "select": {"value": "Status"},
                "where": {"gt": ["Population", 1500]},
            },
            {
                "from": "city",
                "select": {"value": "Status"},
                "where": {"lt": ["Population", 500]},
            },
        ]}
        self.assertEqual(result, expected)

    def test_issue_19a(self):
        # https: // docs.microsoft.com / en - us / sql / t - sql / functions / trim - transact - sql?view = sql - server - ver15
        sql = "select trim(' ' from ' This is a test') from dual"
        result = parse(sql)
        expected = {
            "from": "dual",
            "select": {"value": {
                "trim": {"literal": " This is a test"},
                "characters": {"literal": " "},
            }},
        }
        self.assertEqual(result, expected)

    def test_issue_19b(self):
        sql = "select trim(' testing  ') from dual"
        result = parse(sql)
        expected = {
            "from": "dual",
            "select": {"value": {"trim": {"literal": " testing  "}}},
        }
        self.assertEqual(result, expected)

    def test_except(self):
        sql = """select name from employee
        except
        select 'Alan' from dual
        """
        result = parse(sql)
        expected = {"except": [
            {"from": "employee", "select": {"value": "name"}},
            {"from": "dual", "select": {"value": {"literal": "Alan"}}},
        ]}
        self.assertEqual(result, expected)

    def test_except2(self):
        sql = """select name from employee
        except
        select 'Alan' 
        except
        select 'Paul' 
        """
        result = parse(sql)
        expected = {"except": [
            {"except": [
                {"from": "employee", "select": {"value": "name"}},
                {"select": {"value": {"literal": "Alan"}}},
            ]},
            {"select": {"value": {"literal": "Paul"}}},
        ]}
        self.assertEqual(result, expected)

    def test_issue_41_distinct_on(self):
        #          123456789012345678901234567890
        query = """SELECT DISTINCT ON (col) col, col2 FROM test"""
        result = parse(query)
        expected = {
            "distinct_on": {"value": "col"},
            "from": "test",
            "select": [{"value": "col"}, {"value": "col2"}],
        }
        self.assertEqual(result, expected)

    def test_create_table(self):
        sql = """
        CREATE TABLE warehouses
          (
            warehouse_id NUMBER 
                         GENERATED BY DEFAULT AS IDENTITY START WITH 10 
                         PRIMARY KEY,
            warehouse_name VARCHAR( 255 ) ,
            location_id    NUMBER( 12, 0 ),
            CONSTRAINT fk_warehouses_locations 
              FOREIGN KEY( location_id )
              REFERENCES locations( location_id ) 
              ON DELETE CASCADE
          );
          """
        result = parse(sql)
        expected = {"create table": {
            "columns": [
                {
                    "identity": {"generated": "by_default", "start_with": 10},
                    "name": "warehouse_id",
                    "primary_key": True,
                    "type": {"number": {}},
                },
                {"name": "warehouse_name", "type": {"varchar": 255}},
                {"name": "location_id", "type": {"number": [12, 0]}},
            ],
            "constraint": {
                "foreign_key": {
                    "columns": "location_id",
                    "on_delete": "cascade",
                    "references": {"columns": "location_id", "table": "locations"},
                },
                "name": "fk_warehouses_locations",
            },
            "name": "warehouses",
        }}
        self.assertEqual(result, expected)

    def test_create_table_always(self):
        sql = """
        CREATE TABLE warehouses
          (
            warehouse_id NUMBER 
                         GENERATED ALWAYS AS IDENTITY START WITH 10 
                         PRIMARY KEY
          );
          """
        result = parse(sql)
        expected = {"create table": {
            "name": "warehouses",
            "columns": {
                "identity": {"generated": "always", "start_with": 10},
                "name": "warehouse_id",
                "primary_key": True,
                "type": {"number": {}},
            },
        }}
        self.assertEqual(result, expected)

    def test_lateral_join1(self):
        sql = """SELECT * 
            FROM departments AS d, 
            LATERAL (SELECT * FROM employees) AS iv2
        """
        result = parse(sql)
        expected = {
            "from": [
                {"name": "d", "value": "departments"},
                {"lateral": {
                    "name": "iv2",
                    "value": {"from": "employees", "select": "*"},
                }},
            ],
            "select": "*",
        }
        self.assertEqual(result, expected)

    def test_lateral_join2(self):
        sql = """SELECT * 
            FROM departments AS d
            JOIN LATERAL (SELECT up_seconds / cal_seconds AS up_pct) t3 ON true
        """
        result = parse(sql)
        expected = {
            "from": [
                {"name": "d", "value": "departments"},
                {
                    "join lateral": {
                        "name": "t3",
                        "value": {"select": {
                            "name": "up_pct",
                            "value": {"div": ["up_seconds", "cal_seconds"]},
                        }},
                    },
                    "on": True,
                },
            ],
            "select": "*",
        }
        self.assertEqual(result, expected)

    def test_issue_83_returning(self):
        sql = """INSERT INTO "some_table" ("some_A", "some_B") VALUES ('Foo', 'Bar') RETURNING "some_table"."id" """
        result = parse(sql)
        expected = {
            "insert": "some_table",
            "columns": ["some_A", "some_B"],
            "query": {"select": [
                {"value": {"literal": "Foo"}},
                {"value": {"literal": "Bar"}},
            ]},
            "returning": {"name": "some_table.id", "value": "RETURNING"},
        }
        self.assertEqual(result, expected)

    def test_issue_128_substring(self):
        # https://www.w3resource.com/PostgreSQL/substring-function.php
        sql = """SELECT substring(name from 1 for 5)"""
        result = parse(sql)
        expected = {"select": {"value": {"substring": "name", "from": 1, "for": 5}}}
        self.assertEqual(result, expected)

    def test_issue_129_for_updateA(self):
        sql = """select * from bmsql_config for update;"""
        result = parse(sql)
        expected = {
            "from": "bmsql_config",
            "locking": {"mode": "update"},
            "select": "*",
        }
        self.assertEqual(result, expected)

    def test_issue_129_for_updateB(self):
        sql = """select * from bmsql_config for update of bmsql_config nowait;"""
        result = parse(sql)
        expected = {
            "select": "*",
            "from": "bmsql_config",
            "locking": {
                "mode": "update",
                "table": {"value": "bmsql_config", "nowait": True},
            },
        }
        self.assertEqual(result, expected)

    def test_issue_134a(self):
        # https://www.ibm.com/docs/en/informix-servers/12.10?topic=types-interval-data-type
        sql = """SELECT interval ':1' day (3)"""
        result = parse(sql)
        expect = {"select": {"value": {"cast": [
            {"interval": [1, "minute"]},
            {"day": 3},
        ]}}}
        self.assertEqual(result, expect)

    def test_issue_134b(self):
        # https://www.ibm.com/docs/en/informix-servers/12.10?topic=types-interval-data-type
        sql = """SELECT interval '1:1' minute to second"""
        result = parse(sql)
        expect = {"select": {"value": {"cast": [
            {"add": [{"interval": [1, "hour"]}, {"interval": [1, "minute"]},]},
            {"minute": {}, "second": {}},
        ]}}}
        self.assertEqual(result, expect)

    def test_issue_134c(self):
        # https://www.ibm.com/docs/en/informix-servers/12.10?topic=types-manipulating-datetime-interval-values
        sql = """SELECT interval '1-1' month to second"""
        result = parse(sql)
        expect = {"select": {"value": {"cast": [
            {"add": [{"interval": [1, "year"]}, {"interval": [1, "month"]},]},
            {"month": {}, "second": {}},
        ]}}}
        self.assertEqual(result, expect)

    def test_issue_140_interval_cast1(self):
        sql = """SELECT '2 months'::interval"""
        result = parse(sql)
        expect = {"select": {"value": {"cast": [
            {"literal": "2 months"},
            {"interval": {}},
        ]}}}
        self.assertEqual(result, expect)

    def test_issue_140_interval_cast2(self):
        sql = """SELECT CAST('2 months' AS INTERVAL)"""
        result = parse(sql)
        expect = {"select": {"value": {"cast": [
            {"literal": "2 months"},
            {"interval": {}},
        ]}}}
        self.assertEqual(result, expect)

    def test_issue_144_interval(self):
        sql = """SELECT DATE_ADD(ha, INTERVAL 28+(installment_number-1)*30 DAY)"""
        result = parse(sql)
        expect = {"select": {"value": {"date_add": [
            "ha",
            {"interval": [
                {"add": [28, {"mul": [{"sub": ["installment_number", 1]}, 30]}]},
                "day",
            ]},
        ]}}}
        self.assertEqual(result, expect)

    def test_issue_147_interval1(self):
        sql = "SELECT INTERVAL '1'"
        result = parse(sql)
        expect = {"select": {"value": {"interval": [1, "second"]}}}
        self.assertEqual(result, expect)

    def test_issue_147_interval3(self):
        sql = "SELECT INTERVAL 'P0001-02-03T04:05:06'"
        result = parse(sql)
        expect = {"select": {"value": {"add": [
            {"interval": [1, "year"]},
            {"interval": [2, "month"]},
            {"interval": [3, "day"]},
            {"interval": [4, "hour"]},
            {"interval": [5, "minute"]},
            {"interval": [6, "second"]},
        ]}}}
        self.assertEqual(result, expect)

    def test_issue_147_interval4(self):
        sql = "SELECT INTERVAL 'P1Y2M3DT4H5M6S'"
        result = parse(sql)
        expect = {"select": {"value": {"add": [
            {"interval": [1, "year"]},
            {"interval": [2, "month"]},
            {"interval": [3, "day"]},
            {"interval": [4, "hour"]},
            {"interval": [5, "minute"]},
            {"interval": [6, "second"]},
        ]}}}
        self.assertEqual(result, expect)

    def test_issue_147_interval5(self):
        sql = "SELECT INTERVAL '-1-2 +3 -4:05:06'"
        result = parse(sql)
        expect = {"select": {"value": {"add": [
            {"interval": [-1, "year"]},
            {"interval": [-2, "month"]},
            {"interval": [3, "day"]},
            {"interval": [-4, "hour"]},
            {"interval": [-5, "minute"]},
            {"interval": [-6, "second"]},
        ]}}}
        self.assertEqual(result, expect)

    def test_issue_147_interval6(self):
        sql = "SELECT INTERVAL '-1 year -2 mons +3 days -04:05:06'"
        result = parse(sql)
        expect = {"select": {"value": {"add": [
            {"interval": [-1, "year"]},
            {"interval": [-2, "month"]},
            {"interval": [3, "day"]},
            {"interval": [-4, "hour"]},
            {"interval": [-5, "minute"]},
            {"interval": [-6, "second"]},
        ]}}}
        self.assertEqual(result, expect)

    def test_issue_147_interval7(self):
        sql = "SELECT INTERVAL '@ 1 year 2 mons -3 days 4 hours 5 mins 6 secs ago'"
        result = parse(sql)
        expect = {"select": {"value": {"add": [
            {"interval": [-1, "year"]},
            {"interval": [-2, "month"]},
            {"interval": [3, "day"]},
            {"interval": [-4, "hour"]},
            {"interval": [-5, "minute"]},
            {"interval": [-6, "second"]},
        ]}}}
        self.assertEqual(result, expect)

    def test_issue_147_interval8(self):
        sql = "SELECT INTERVAL 'P-1Y-2M3DT-4H-5M-6S'"
        result = parse(sql)
        expect = {"select": {"value": {"add": [
            {"interval": [-1, "year"]},
            {"interval": [-2, "month"]},
            {"interval": [3, "day"]},
            {"interval": [-4, "hour"]},
            {"interval": [-5, "minute"]},
            {"interval": [-6, "second"]},
        ]}}}
        self.assertEqual(result, expect)

    def test_issue_149_insert(self):
        sql = """WITH delta AS (
            SELECT * from ta
        )
        INSERT INTO tb
        SELECT * FROM delta;"""
        result = parse(sql)
        expect = {
            "with": {"name": "delta", "value": {"from": "ta", "select": "*"}},
            "insert": "tb",
            "query": {"from": "delta", "select": "*"},
        }
        self.assertEqual(result, expect)

    def test_issue_154_millisecond(self):
        sql = """SELECT
            DISTINCT
            m AS mesa,
            COALESCE(
                LEAD(
                    TIMESTAMP_SUB(systema, INTERVAL 1 MILLISECOND)
                ) OVER (PARTITION BY id ORDER BY systema ASC),
                TIMESTAMP('9999-12-31 23:59:59.999')) AS end_at,
            airflow_metad AS synced_at
        FROM
            `projeto.dataset.tabela` TABLESAMPLE SYSTEM (0.1 PERCENT)
        QUALIFY ROW_NUMBER() OVER (PARTITION BY id, systema) = 1
        LIMIT 50000"""
        result = parse(sql)
        expect = {
            "from": {
                "tablesample": {"method": "system", "percent": 0.1},
                "value": "projeto..dataset..tabela",
            },
            "limit": 50000,
            "qualify": {"eq": [
                {
                    "over": {"partitionby": ["id", "systema"]},
                    "value": {"row_number": {}},
                },
                1,
            ]},
            "select_distinct": [
                {"name": "mesa", "value": "m"},
                {
                    "name": "end_at",
                    "value": {"coalesce": [
                        {
                            "value": {"lead": {"timestamp_sub": [
                                "systema",
                                {"interval": [1, "millisecond"]},
                            ]}},
                            "over": {
                                "orderby": {"sort": "asc", "value": "systema"},
                                "partitionby": "id",
                            },
                        },
                        {"timestamp": {"literal": "9999-12-31 23:59:59.999"}},
                    ]},
                },
                {"name": "synced_at", "value": "airflow_metad"},
            ],
        }

        self.assertEqual(result, expect)
