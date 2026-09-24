"""
Product data transformation service for RAG ingestion.

Transforms product catalog data into RAG-optimized text chunks.
"""
from typing import Any
from app.core import logger


class ProductTransformer:
    """Transform product data into RAG-friendly text chunks."""

    def transform_product_to_chunks(
        self,
        product: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """
        Transform a product into multiple searchable chunks.

        Creates comprehensive text representations optimized for Vietnamese e-commerce:
        1. Main product description (name + key attributes)
        2. Detailed product information (purpose + usage)
        3. Customer targeting information (segment + age + origin)

        Args:
            product: Product dictionary from data-service

        Returns:
            List of chunk dictionaries ready for RAG ingestion
        """
        chunks = []
        product_id = str(product.get("product_id", ""))
        product_name = product.get("name", "")
        brand_name = product.get("brand_name") or "Không có thương hiệu"

        # Skip if no name
        if not product_name:
            logger.warning("Skipping product with no name", extra={"product_id": product_id})
            return []

        # Extract all fields
        origin = self._format_origin(product.get("origin"))
        customer_segment = self._format_customer_segment(product.get("customer_segment"))
        customer_age = self._format_customer_age(product.get("customer_age"))
        product_purpose = product.get("product_purpose") or ""
        how_use = product.get("how_use") or ""
        price = product.get("price")
        stock_quantity = product.get("stock_quantity", 0)

        # Format price
        price_str = f"{int(price):,}đ" if price else "Liên hệ"

        # Chunk 1: Main product overview (optimized for product search)
        main_text = f"Sản phẩm: {product_name}\n"
        main_text += f"Thương hiệu: {brand_name}\n"
        if origin:
            main_text += f"Xuất xứ: {origin}\n"
        main_text += f"Giá: {price_str}\n"
        if customer_segment:
            main_text += f"Đối tượng: {customer_segment}\n"
        if customer_age:
            main_text += f"Độ tuổi: {customer_age}"

        chunks.append({
            "id": f"{product_id}_main",
            "text": main_text.strip(),
            "metadata": {
                "source": "product_catalog",
                "product_id": product_id,
                "product_name": product_name,
                "brand_name": brand_name,
                "chunk_type": "main_info",
                "origin": product.get("origin"),
                "customer_segment": product.get("customer_segment"),
                "customer_age": product.get("customer_age"),
                "price": float(price) if price else None,
                "stock_quantity": stock_quantity,
                "lang": "vi",
                "chunk_index": 0,
                "total_chunks": 0,  # Will be updated later
                "extra": {}
            }
        })

        # Chunk 2: Product purpose and benefits (if available)
        if product_purpose:
            purpose_text = f"Công dụng của {product_name}:\n{product_purpose}"
            chunks.append({
                "id": f"{product_id}_purpose",
                "text": purpose_text,
                "metadata": {
                    "source": "product_catalog",
                    "product_id": product_id,
                    "product_name": product_name,
                    "brand_name": brand_name,
                    "chunk_type": "purpose",
                    "origin": product.get("origin"),
                    "customer_segment": product.get("customer_segment"),
                    "customer_age": product.get("customer_age"),
                    "price": float(price) if price else None,
                    "stock_quantity": stock_quantity,
                    "lang": "vi",
                    "chunk_index": 1,
                    "total_chunks": 0,
                    "extra": {}
                }
            })

        # Chunk 3: Usage instructions (if available)
        if how_use:
            usage_text = f"Cách sử dụng {product_name}:\n{how_use}"
            chunks.append({
                "id": f"{product_id}_usage",
                "text": usage_text,
                "metadata": {
                    "source": "product_catalog",
                    "product_id": product_id,
                    "product_name": product_name,
                    "brand_name": brand_name,
                    "chunk_type": "usage",
                    "origin": product.get("origin"),
                    "customer_segment": product.get("customer_segment"),
                    "customer_age": product.get("customer_age"),
                    "price": float(price) if price else None,
                    "stock_quantity": stock_quantity,
                    "lang": "vi",
                    "chunk_index": 2,
                    "total_chunks": 0,
                    "extra": {}
                }
            })

        # Update total_chunks for all chunks
        total_chunks = len(chunks)
        for chunk in chunks:
            chunk["metadata"]["total_chunks"] = total_chunks

        logger.info(
            "Product transformed to chunks",
            extra={
                "product_id": product_id,
                "product_name": product_name,
                "chunks_created": len(chunks)
            }
        )

        return chunks

    @staticmethod
    def _format_origin(origin: str | None) -> str:
        """Format product origin for Vietnamese display."""
        if not origin:
            return ""

        origin_map = {
            "usa": "Mỹ",
            "ireland": "Ireland",
            "singapore": "Singapore",
            "vietnam": "Việt Nam",
            "netherlands": "Hà Lan"
        }
        return origin_map.get(origin, origin.title())

    @staticmethod
    def _format_customer_segment(segment: str | None) -> str:
        """Format customer segment for Vietnamese display."""
        if not segment:
            return ""

        segment_map = {
            "children": "Trẻ em",
            "elderly": "Người cao tuổi",
            "women": "Phụ nữ",
            "patients": "Bệnh nhân",
            "breastfeeding_mothers": "Mẹ cho con bú",
            "pregnant_mothers": "Mẹ bầu",
            "diabetic": "Người tiểu đường",
            "general": "Mọi đối tượng"
        }
        return segment_map.get(segment, segment.replace("_", " ").title())

    @staticmethod
    def _format_customer_age(age: str | None) -> str:
        """Format customer age range for Vietnamese display."""
        if not age:
            return ""

        age_map = {
            "age_0m_6m": "0-6 tháng",
            "age_6m_36m": "6-36 tháng",
            "age_4y_12y": "4-12 tuổi",
            "age_13y_17y": "13-17 tuổi",
            "age_18y_40y": "18-40 tuổi",
            "age_41y_60y": "41-60 tuổi",
            "age_60y_plus": "Trên 60 tuổi",
            "all_ages": "Mọi lứa tuổi"
        }
        return age_map.get(age, age.replace("_", " ").title())


# Global product transformer instance
product_transformer = ProductTransformer()
