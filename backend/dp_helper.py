import os
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    Numeric,
    String,
    create_engine,
    event,
    select,
)
from sqlalchemy.orm import declarative_base, sessionmaker


Base = declarative_base()

MENU = [
    ("Pav Bhaji", "6.00"),
    ("Chole Bhature", "7.00"),
    ("Pizza", "8.00"),
    ("Mango Lassi", "5.00"),
    ("Masala Dosa", "6.00"),
    ("Vegetable Biryani", "9.00"),
    ("Vada Pav", "4.00"),
    ("Rava Dosa", "7.00"),
    ("Samosa", "5.00"),
]


class Food(Base):
    __tablename__ = "mira_food"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)
    price = Column(Numeric(10, 2), nullable=False)


class Cart(Base):
    __tablename__ = "mira_cart"

    session = Column(String(255), primary_key=True)
    items = Column(JSON, nullable=False, default=dict)


class Order(Base):
    __tablename__ = "mira_order"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session = Column(String(255), nullable=False)
    status = Column(String(40), nullable=False, default="in progress")
    total = Column(Numeric(10, 2), nullable=False)


class OrderItem(Base):
    __tablename__ = "mira_order_item"

    order_id = Column(
        Integer,
        ForeignKey("mira_order.id"),
        primary_key=True,
    )
    food_id = Column(
        Integer,
        ForeignKey("mira_food.id"),
        primary_key=True,
    )
    quantity = Column(Integer, nullable=False)
    unit_price = Column(Numeric(10, 2), nullable=False)


class Interaction(Base):
    __tablename__ = "mira_interaction"

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
    )
    source = Column(String(40), nullable=False)
    action = Column(String(40), nullable=False)
    success = Column(Boolean, nullable=False)


database_path = Path(__file__).resolve().parents[1] / "mira.db"

url = os.getenv(
    "DATABASE_URL",
    "sqlite:///" + str(database_path),
)

engine_options = {"pool_pre_ping": True}

if url.startswith("sqlite"):
    engine_options["connect_args"] = {
        "check_same_thread": False,
        "timeout": 20,
    }

engine = create_engine(url, **engine_options)


if url.startswith("sqlite"):

    @event.listens_for(engine, "connect")
    def sqlite_connect(connection, record):
        connection.isolation_level = None
        connection.execute("PRAGMA foreign_keys=ON")

    @event.listens_for(engine, "begin")
    def sqlite_begin(connection):
        # Serialize short transactions, including repeated checkout.
        connection.exec_driver_sql("BEGIN IMMEDIATE")


Session = sessionmaker(engine, expire_on_commit=False)


def initialize():
    """Create application tables and seed the menu on first startup."""
    Base.metadata.create_all(engine)

    with Session.begin() as db:
        if not db.scalar(select(Food.id).limit(1)):
            db.add_all(
                [
                    Food(name=name, price=Decimal(price))
                    for name, price in MENU
                ]
            )


def record_interaction(source, action, success):
    """Record request metadata without storing conversation text."""
    with Session.begin() as db:
        db.add(
            Interaction(
                source=source,
                action=action,
                success=success,
            )
        )


def menu():
    with Session() as db:
        foods = db.scalars(select(Food).order_by(Food.id))

        return [
            {"name": food.name, "price": str(food.price)}
            for food in foods
        ]


def normalize(name):
    if not isinstance(name, str):
        raise ValueError("Please specify a food name.")

    canonical = {
        food_name.lower(): food_name
        for food_name, _ in MENU
    }

    canonical.update(
        {
            "biryani": "Vegetable Biryani",
            "pizzas": "Pizza",
        }
    )

    key = name.strip().lower()

    if key not in canonical:
        raise ValueError(
            f"{name} is not on the menu. Please choose a listed item."
        )

    return canonical[key]


def quantity(value):
    if isinstance(value, bool):
        raise ValueError(
            "Quantities must be whole numbers from 1 to 99."
        )

    try:
        number = Decimal(str(value))

        if (
            not number.is_finite()
            or number != number.to_integral_value()
            or not 1 <= number <= 99
        ):
            raise ValueError

        return int(number)

    except (ValueError, ArithmeticError):
        raise ValueError(
            "Quantities must be whole numbers from 1 to 99."
        ) from None


def cart_action(session, action, names=None, numbers=None):
    names = names or []
    numbers = numbers or []

    # Validate the entire request before changing the cart.
    if action == "add":
        if not names or len(names) != len(numbers):
            raise ValueError(
                "Please specify a quantity for every food item."
            )

        changes = [
            (normalize(name), quantity(count))
            for name, count in zip(names, numbers)
        ]

    elif action == "remove":
        if not names:
            raise ValueError("Which food item should I remove?")

        changes = [(normalize(name), 0) for name in names]

    else:
        changes = []

    with Session.begin() as db:
        cart = db.scalar(
            select(Cart)
            .where(Cart.session == session)
            .with_for_update()
        )

        if cart is None:
            cart = Cart(session=session, items={})
            db.add(cart)

        items = dict(cart.items)

        if action == "new":
            items = {}

        for name, count in changes:
            if action == "add":
                items[name] = quantity(items.get(name, 0) + count)
            else:
                items.pop(name, None)

        if action == "complete":
            if not items:
                raise ValueError(
                    "Your order is empty. Add a food item first."
                )

            foods = {
                food.name: food
                for food in db.scalars(select(Food))
            }

            total = sum(
                (
                    foods[name].price * count
                    for name, count in items.items()
                ),
                Decimal("0"),
            )

            order = Order(
                session=session,
                total=total,
                status="in progress",
            )

            db.add(order)
            db.flush()

            db.add_all(
                [
                    OrderItem(
                        order_id=order.id,
                        food_id=foods[name].id,
                        quantity=count,
                        unit_price=foods[name].price,
                    )
                    for name, count in items.items()
                ]
            )

            cart.items = {}

            return {
                "order_id": order.id,
                "total": f"{total:.2f}",
                "status": order.status,
            }

        cart.items = items

        return {"items": items}


def track(order_id):
    try:
        value = Decimal(str(order_id))

        if (
            not value.is_finite()
            or value != value.to_integral_value()
            or value <= 0
        ):
            raise ValueError

        order_id = int(value)

    except (ValueError, ArithmeticError):
        raise ValueError(
            "Please provide a positive whole-number order ID."
        ) from None

    with Session() as db:
        order = db.get(Order, order_id)

        if order is None:
            raise ValueError(
                f"No order found with ID {order_id}."
            )

        return {
            "order_id": order.id,
            "total": str(order.total),
            "status": order.status,
        }
