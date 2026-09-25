<remind>
File này lưu HỒ SƠ KHAI THÁC của từng user: tên, sở thích, trẻ con mấy tuổi, thương hiệu sữa ưa dùng, lịch sử mua hàng.

**Mục đích:** AI đọc file này đầu mỗi phiên để cá nhân hóa lời tư vấn. VD: biết khách hay mua dòng sữa nào thì ưu tiên gợi ý dòng đó trước.

**Per-user:** Mỗi user_id có USER.md riêng lưu trong DB (bảng `user_prompts`). KHÔNG dùng chung 1 file.

**Khi cập nhật:**
- Xem trước: `view_personal_profile(user_id, "USER.md")`
- Thêm thông tin mới: `edit_personal_profile(user_id, "USER.md", command="append", content="...")`
- Sửa thông tin cũ: `edit_personal_profile(user_id, "USER.md", command="str_replace", old_str="...", new_str="...")`
- Xóa thông tin sai: `edit_personal_profile(user_id, "USER.md", command="delete", old_str="...")`
- VD: user nói "bé giờ 12 tháng rồi" → view trước → str_replace "5 tháng" → "12 tháng"

**Cấu trúc chuẩn:**
- `customer_name`: Tên khách
- `customer_age`: Tuổi
- `preferred_brands`: Thương hiệu hiện dùng
- `purchase_history`: Các sản phẩm đã mua
- `notes`: Ghi chú đặc biệt (dị ứng, sở thích giá...)
</remind>