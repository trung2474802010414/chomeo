"""
core/paginator.py
Tập trung chuyên sâu vào:
1. Custom Iterator (`__iter__`, `__next__`, `StopIteration`) để duyệt dữ liệu theo từng trang (Page).
2. Generator Pipeline (`yield`, Generator Expressions) để lọc đa điều kiện (từ khóa, danh mục,
   loài thú cưng, khoảng giá) mà không tạo ra các danh sách trung gian gây tốn bộ nhớ.
3. Streaming CSV/JSON Export & Import bằng Generator và List/Dict Comprehension.
"""

import csv
import io
import itertools
from typing import Any, Callable, Dict, Generator, Iterable, Iterator, List, Optional


class PageIterator(Iterator[List[Any]]):
    """
    Custom Iterator tự định nghĩa theo chuẩn Iterator Protocol của Python:
    - Phải cài đặt `__iter__(self)` trả về chính nó (`self`).
    - Phải cài đặt `__next__(self)` trả về trang tiếp theo (một list các phần tử)
      hoặc ném ra `StopIteration` khi đã hết dữ liệu.

    Điểm mạnh:
    Nhận đầu vào là bất kỳ `Iterable` nào (kể cả một Generator đang stream từ SQLite)
    và dùng `itertools.islice` để cắt đúng `page_size` phần tử mỗi lần gọi `next()`.
    """

    def __init__(self, iterable: Iterable[Any], page_size: int = 6):
        if page_size <= 0:
            raise ValueError("page_size phải lớn hơn 0")
        self._iterator = iter(iterable)
        self.page_size = page_size
        self.current_page_number = 0

    def __iter__(self) -> "PageIterator":
        return self

    def __next__(self) -> List[Any]:
        # Lấy tối đa `page_size` phần tử tiếp theo từ iterator gốc
        chunk = list(itertools.islice(self._iterator, self.page_size))
        if not chunk:
            raise StopIteration
        self.current_page_number += 1
        return chunk


def paginate_stream(
    stream: Iterable[Dict[str, Any]],
    page: int = 1,
    page_size: int = 6,
) -> Dict[str, Any]:
    """
    Sử dụng `PageIterator` để phân trang từ một dòng dữ liệu (Generator/Iterable).
    Trả về dữ liệu của trang được yêu cầu cùng tổng số bản ghi và tổng số trang.
    """
    page = max(1, page)
    page_iterator = PageIterator(stream, page_size=page_size)

    selected_items: List[Dict[str, Any]] = []
    total_items = 0
    total_pages = 0

    # Duyệt qua PageIterator (gọi ngầm __iter__ và __next__ cho đến khi gặp StopIteration)
    for page_num, chunk in enumerate(page_iterator, start=1):
        total_pages = page_num
        total_items += len(chunk)
        if page_num == page:
            selected_items = chunk

    return {
        "items": selected_items,
        "page": page,
        "page_size": page_size,
        "total_items": total_items,
        "total_pages": max(1, total_pages),
        "has_prev": page > 1,
        "has_next": page < total_pages,
    }


def build_filter_pipeline(
    source_stream: Iterable[Any],
    keyword: Optional[str] = None,
    category: Optional[str] = None,
    pet_type: Optional[str] = None,
    breed: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    in_stock_only: bool = False,
    transform_fn: Optional[Callable[[Any], Dict[str, Any]]] = None,
) -> Generator[Dict[str, Any], None, None]:
    """
    Generator Pipeline nối tiếp nhau (Chained Generators):
    Mỗi bước lọc là một Generator Expression `(x for x in stream if ...)`.
    Dữ liệu đi qua đường ống từng phần tử một (lazy evaluation) thay vì tạo nhiều list tạm.
    """
    pipeline: Iterable[Any] = source_stream

    if keyword:
        kw = keyword.strip().lower()
        pipeline = (
            item for item in pipeline
            if kw in getattr(item, "name", "").lower()
            or kw in getattr(item, "description", "").lower()
            or kw in getattr(item, "breed", "").lower()
        )

    if category and category != "ALL":
        pipeline = (item for item in pipeline if getattr(item, "category", "") == category)

    if pet_type and pet_type != "ALL":
        pipeline = (
            item for item in pipeline
            if getattr(item, "pet_type", "") in (pet_type, "Chó & Mèo")
        )

    if breed and breed != "ALL":
        br = breed.strip().lower()
        pipeline = (
            item for item in pipeline
            if br in getattr(item, "breed", "").lower()
            or br in getattr(item, "name", "").lower()
            or br in getattr(item, "description", "").lower()
        )

    if min_price is not None:
        pipeline = (item for item in pipeline if getattr(item, "price", 0) >= min_price)

    if max_price is not None:
        pipeline = (item for item in pipeline if getattr(item, "price", 0) <= max_price)

    if in_stock_only:
        pipeline = (item for item in pipeline if getattr(item, "stock", 0) > 0)

    # Bước cuối của pipeline: chuyển đổi đối tượng Model thành dict
    for item in pipeline:
        if transform_fn is not None:
            yield transform_fn(item)
        elif hasattr(item, "to_dict"):
            yield item.to_dict()
        else:
            yield dict(item)


def stream_csv_export(
    records: Iterable[Dict[str, Any]],
    fieldnames: List[str],
) -> Generator[str, None, None]:
    """
    Generator xuất từng dòng CSV.
    Rất hữu ích khi xuất hàng chục nghìn sản phẩm/đơn hàng mà không cần ghép một chuỗi khổng lồ.
    """
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fieldnames, extrasaction="ignore")

    # Yield dòng tiêu đề cột trước
    writer.writeheader()
    yield buffer.getvalue()
    buffer.seek(0)
    buffer.truncate(0)

    # Yield từng dòng dữ liệu khi duyệt qua Iterable/Generator đầu vào
    for row in records:
        writer.writerow(row)
        yield buffer.getvalue()
        buffer.seek(0)
        buffer.truncate(0)


def parse_csv_stream(csv_text: str) -> Generator[Dict[str, Any], None, None]:
    """
    Generator đọc nội dung CSV tải lên theo từng dòng và làm sạch khoảng trắng thừa
    bằng Dict Comprehension.
    """
    reader = csv.DictReader(io.StringIO(csv_text.strip()))
    for raw_row in reader:
        # Dict Comprehension: chuẩn hóa key và value trên mỗi dòng CSV
        cleaned_row = {
            k.strip(): (v.strip() if isinstance(v, str) else v)
            for k, v in raw_row.items()
            if k is not None
        }
        if any(cleaned_row.values()):
            yield cleaned_row
