import enum
import uuid

from sqlalchemy import NUMERIC, INTEGER, TEXT, VARCHAR, TIMESTAMP, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, ENUM as PgEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.database import Base


class CustomerSegment(str, enum.Enum):
    children = "children"
    elderly = "elderly"
    women = "women"
    patients = "patients"
    breastfeeding_mothers = "breastfeeding_mothers"
    pregnant_mothers = "pregnant_mothers"
    diabetic = "diabetic"
    general = "general"


class CustomerAge(str, enum.Enum):
    age_0m_6m = "age_0m_6m"
    age_6m_36m = "age_6m_36m"
    age_4y_12y = "age_4y_12y"
    age_13y_17y = "age_13y_17y"
    age_18y_40y = "age_18y_40y"
    age_41y_60y = "age_41y_60y"
    age_60y_plus = "age_60y_plus"
    all_ages = "all_ages"


class ProductOrigin(str, enum.Enum):
    usa = "usa"
    ireland = "ireland"
    singapore = "singapore"
    vietnam = "vietnam"
    netherlands = "netherlands"


class Brand(Base):
    __tablename__ = "brands"

    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )
    name: Mapped[str] = mapped_column(VARCHAR(100), unique=True, nullable=False)
    created_at: Mapped[object] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now(),
    )
    products: Mapped[list["Product"]] = relationship(back_populates="brand")


class Product(Base):
    __tablename__ = "products"

    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(TEXT, nullable=False)
    brand_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("brands.brand_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    brand: Mapped["Brand | None"] = relationship(back_populates="products")
    origin: Mapped[ProductOrigin | None] = mapped_column(PgEnum(ProductOrigin, name="product_origin", create_type=False), nullable=True)
    customer_segment: Mapped[CustomerSegment | None] = mapped_column(PgEnum(CustomerSegment, name="customer_segment", create_type=False), nullable=True)
    customer_age: Mapped[CustomerAge | None] = mapped_column(PgEnum(CustomerAge, name="customer_age", create_type=False), nullable=True)
    product_purpose: Mapped[str | None] = mapped_column(TEXT, nullable=True)
    how_use: Mapped[str | None] = mapped_column(TEXT, nullable=True)
    price: Mapped[int | None] = mapped_column(NUMERIC(12, 0), nullable=True)
    stock_quantity: Mapped[int] = mapped_column(INTEGER, nullable=False, default=100)
    created_at: Mapped[object] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[object] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
