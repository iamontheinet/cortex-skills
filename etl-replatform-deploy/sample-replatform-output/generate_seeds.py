#!/usr/bin/env python3
"""
Generate large synthetic seed CSV files for the Contoso Retail sample
Replatform output. Uses only Python stdlib — no external dependencies.

Usage:
    python generate_seeds.py [--scale N]

    --scale N  Multiplier for row counts (default 1). Use 10 for stress testing.

Output:
    Creates seeds/ directories with CSV files inside each dbt project.
"""

import csv
import os
import random
import sys
from datetime import date, datetime, timedelta

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BASE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "Output", "ETL")

SCALE = 1  # override via --scale

# Row counts (at scale=1)
NUM_CUSTOMERS = 10_000
NUM_ORDERS = 50_000
AVG_LINES_PER_ORDER = 3      # → ~150K order_details
NUM_INVENTORY = 25_000
NUM_AUDIT = 50_000
NUM_DAILY_AGG_DAYS = 365      # 1 year

# Reference data
REGIONS = ["Northeast", "Southeast", "Midwest", "Southwest",
           "West", "Northwest", "Mid-Atlantic", "Pacific"]
WAREHOUSE_CODES = [f"WH-{i:03d}" for i in range(1, 51)]  # 50 warehouses
EVENT_TYPES = ["LOGIN", "LOGOUT", "INSERT", "UPDATE", "DELETE",
               "EXPORT", "IMPORT", "APPROVAL", "REJECTION", "ERROR"]
FIRST_NAMES = [
    "James", "Mary", "Robert", "Patricia", "John", "Jennifer", "Michael",
    "Linda", "David", "Elizabeth", "William", "Barbara", "Richard", "Susan",
    "Joseph", "Jessica", "Thomas", "Sarah", "Christopher", "Karen",
    "Charles", "Lisa", "Daniel", "Nancy", "Matthew", "Betty", "Anthony",
    "Margaret", "Mark", "Sandra", "Donald", "Ashley", "Steven", "Emily",
    "Paul", "Donna", "Andrew", "Michelle", "Joshua", "Carol",
]
LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller",
    "Davis", "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez",
    "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Jackson", "Martin",
    "Lee", "Perez", "Thompson", "White", "Harris", "Sanchez", "Clark",
    "Ramirez", "Lewis", "Robinson", "Walker", "Young", "Allen", "King",
    "Wright", "Scott", "Torres", "Nguyen", "Hill", "Flores",
]
DOMAINS = ["gmail.com", "yahoo.com", "outlook.com", "contoso.com",
           "hotmail.com", "aol.com", "icloud.com", "protonmail.com"]
USERS = ["admin", "etl_service", "analyst_1", "analyst_2", "dba",
         "scheduler", "sync_agent", "report_bot", "audit_svc", "ops_lead"]


def scaled(n: int) -> int:
    return int(n * SCALE)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def random_date(start: date, end: date) -> date:
    delta = (end - start).days
    return start + timedelta(days=random.randint(0, delta))


def random_timestamp(start: date, end: date) -> str:
    d = random_date(start, end)
    h = random.randint(0, 23)
    m = random.randint(0, 59)
    s = random.randint(0, 59)
    return f"{d} {h:02d}:{m:02d}:{s:02d}"


def ensure_dir(path: str) -> str:
    os.makedirs(path, exist_ok=True)
    return path


def write_csv(path: str, headers: list[str], rows: list, label: str):
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(rows)
    size_mb = os.path.getsize(path) / (1024 * 1024)
    print(f"  {label}: {len(rows):>10,} rows  ({size_mb:.1f} MB)  → {path}")


# ---------------------------------------------------------------------------
# Generators
# ---------------------------------------------------------------------------

def gen_customers(seed_dir: str) -> list[int]:
    """Generate customers.csv. Returns list of customer_ids."""
    n = scaled(NUM_CUSTOMERS)
    ids = list(range(1, n + 1))
    rows = []
    for cid in ids:
        first = random.choice(FIRST_NAMES)
        last = random.choice(LAST_NAMES)
        name = f"{first} {last}"
        domain = random.choice(DOMAINS)
        email = f"{first.lower()}.{last.lower()}{cid}@{domain}"
        region = random.choice(REGIONS)
        rows.append([cid, name, email, region])

    write_csv(
        os.path.join(seed_dir, "customers.csv"),
        ["customer_id", "customer_name", "email", "region"],
        rows, "customers"
    )
    return ids


def gen_orders(seed_dir: str, customer_ids: list[int]) -> list[int]:
    """Generate orders.csv. Returns list of order_ids."""
    n = scaled(NUM_ORDERS)
    start = date(2023, 1, 1)
    end = date(2024, 12, 31)
    rows = []
    for oid in range(1, n + 1):
        cid = random.choice(customer_ids)
        odate = random_date(start, end)
        # Log-normal distribution for realistic revenue skew
        amount = round(random.lognormvariate(4.0, 1.2), 2)
        amount = min(amount, 99999.99)  # cap
        rows.append([oid, cid, odate.isoformat(), amount])

    write_csv(
        os.path.join(seed_dir, "orders.csv"),
        ["order_id", "customer_id", "order_date", "total_amount"],
        rows, "orders"
    )
    return list(range(1, n + 1))


def gen_order_details(seed_dir: str, order_ids: list[int]) -> None:
    """Generate order_details.csv with ~AVG_LINES_PER_ORDER per order."""
    rows = []
    detail_id = 1
    num_products = 5000  # product_id range

    for oid in order_ids:
        num_lines = max(1, int(random.expovariate(1.0 / AVG_LINES_PER_ORDER)))
        num_lines = min(num_lines, 15)  # cap at 15 lines
        for _ in range(num_lines):
            pid = random.randint(1, num_products)
            qty = random.randint(1, 20)
            price = round(random.uniform(1.99, 499.99), 2)
            rows.append([detail_id, oid, pid, qty, price])
            detail_id += 1

    write_csv(
        os.path.join(seed_dir, "order_details.csv"),
        ["order_detail_id", "order_id", "product_id", "quantity", "unit_price"],
        rows, "order_details"
    )


def gen_inventory(seed_dir: str) -> None:
    """Generate inventory_levels.csv."""
    n = scaled(NUM_INVENTORY)
    rows = []
    start = date(2024, 1, 1)
    end = date(2024, 12, 31)
    num_products = 5000

    seen = set()
    for _ in range(n):
        # Unique (product_id, warehouse_code) pairs
        while True:
            pid = random.randint(1, num_products)
            wh = random.choice(WAREHOUSE_CODES)
            key = (pid, wh)
            if key not in seen:
                seen.add(key)
                break
            if len(seen) >= num_products * len(WAREHOUSE_CODES):
                break  # all combinations used

        # Realistic inventory: ~5% zero, ~15% low, rest normal/high
        r = random.random()
        if r < 0.05:
            qty = 0
        elif r < 0.20:
            qty = random.randint(1, 9)
        elif r < 0.80:
            qty = random.randint(10, 99)
        else:
            qty = random.randint(100, 5000)

        counted = random_date(start, end)
        rows.append([pid, wh, qty, counted.isoformat()])

    write_csv(
        os.path.join(seed_dir, "inventory_levels.csv"),
        ["product_id", "warehouse_code", "quantity_on_hand", "last_counted_date"],
        rows, "inventory_levels"
    )


def gen_audit_log(seed_dir: str) -> None:
    """Generate audit_log.csv."""
    n = scaled(NUM_AUDIT)
    rows = []
    start = date(2023, 1, 1)
    end = date(2024, 12, 31)

    for aid in range(1, n + 1):
        etype = random.choice(EVENT_TYPES)
        ts = random_timestamp(start, end)
        user = random.choice(USERS)
        # Details vary by event type
        if etype in ("INSERT", "UPDATE", "DELETE"):
            table = random.choice(["orders", "customers", "inventory_levels",
                                   "control_variables", "audit_log"])
            details = f"{etype} on {table}: {random.randint(1, 1000)} rows affected"
        elif etype == "ERROR":
            details = f"Error code {random.randint(1000, 9999)}: operation failed"
        elif etype in ("LOGIN", "LOGOUT"):
            details = f"Session {random.randint(100000, 999999)}"
        else:
            details = f"{etype} operation completed successfully"
        rows.append([aid, etype, ts, user, details])

    write_csv(
        os.path.join(seed_dir, "audit_log.csv"),
        ["audit_id", "event_type", "event_timestamp", "user_name", "details"],
        rows, "audit_log"
    )


def gen_fct_daily_orders(seed_dir: str) -> None:
    """Generate fct_daily_orders.csv — pre-aggregated daily data.
    This simulates the output of DailyOrderLoad that MonthlyReportGen reads."""
    n = scaled(NUM_DAILY_AGG_DAYS)
    rows = []
    start = date(2024, 1, 1)

    for i in range(n):
        d = start + timedelta(days=i)
        # Weekend dip
        is_weekend = d.weekday() >= 5
        base_orders = random.randint(30, 80) if is_weekend else random.randint(100, 300)
        unique_cust = int(base_orders * random.uniform(0.6, 0.95))
        gross_rev = round(base_orders * random.uniform(45.0, 120.0), 2)
        avg_val = round(gross_rev / base_orders, 2)
        loaded = f"{d} 06:00:00"
        rows.append([d.isoformat(), base_orders, unique_cust, gross_rev, avg_val, loaded])

    write_csv(
        os.path.join(seed_dir, "fct_daily_orders.csv"),
        ["order_date", "total_orders", "unique_customers",
         "gross_revenue", "avg_order_value", "_loaded_at"],
        rows, "fct_daily_orders"
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    global SCALE
    if "--scale" in sys.argv:
        idx = sys.argv.index("--scale")
        SCALE = float(sys.argv[idx + 1])

    random.seed(42)  # reproducible

    print(f"Generating seed data (scale={SCALE})...\n")

    # 1. DailyOrderLoad / LoadCustomers
    print("Package: DailyOrderLoad / LoadCustomers")
    seed_dir = ensure_dir(os.path.join(
        BASE_DIR, "DailyOrderLoad", "LoadCustomers", "seeds"))
    customer_ids = gen_customers(seed_dir)

    # 2. DailyOrderLoad / LoadOrders
    print("\nPackage: DailyOrderLoad / LoadOrders")
    seed_dir = ensure_dir(os.path.join(
        BASE_DIR, "DailyOrderLoad", "LoadOrders", "seeds"))
    order_ids = gen_orders(seed_dir, customer_ids)
    gen_order_details(seed_dir, order_ids)

    # 3. WeeklyInventorySync / SyncInventory
    print("\nPackage: WeeklyInventorySync / SyncInventory")
    seed_dir = ensure_dir(os.path.join(
        BASE_DIR, "WeeklyInventorySync", "SyncInventory", "seeds"))
    gen_inventory(seed_dir)

    # 4. WeeklyInventorySync / AuditLog
    print("\nPackage: WeeklyInventorySync / AuditLog")
    seed_dir = ensure_dir(os.path.join(
        BASE_DIR, "WeeklyInventorySync", "AuditLog", "seeds"))
    gen_audit_log(seed_dir)

    # 5. MonthlyReportGen / GenerateReport
    print("\nPackage: MonthlyReportGen / GenerateReport")
    seed_dir = ensure_dir(os.path.join(
        BASE_DIR, "MonthlyReportGen", "GenerateReport", "seeds"))
    gen_fct_daily_orders(seed_dir)

    print("\nDone! Seed files generated.")
    print("\nTo load seeds after deploying, run:")
    print("  EXECUTE DBT PROJECT <schema>.<project> ARGS = 'seed';")


if __name__ == "__main__":
    main()
