import unittest
import os
import sys

# Đảm bảo đường dẫn import tới thư mục gốc của project
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.models.state import AgentState
from app.agents.perception import traffic_perception_agent
from app.services.geocoding_service import geocode_street, HCMC_STREET_GAZETTEER


class TestTrafficPerceptionAgent(unittest.TestCase):
    """
    Bộ kiểm thử tự động cho Tác tử Cảm nhận Giao thông (Traffic Perception Agent).
    Kiểm thử khả năng đọc hiểu bản tin tiếng Việt, trích xuất thực thể và chuyển đổi tọa độ.
    """

    def setUp(self):
        """Khởi tạo trạng thái AgentState mẫu trước mỗi test case."""
        self.base_state: AgentState = {
            "scenario_id": 1,
            "user_query": "Tìm đường từ Chợ Bến Thành sang Crescent Mall Quận 7",
            "news_context": "",
            "origin": [10.7725, 106.6980],
            "destination": [10.7292, 106.7197],
            "perceived_hazards": [],
            "avoid_points": [],
            "current_route": None,
            "reflection_count": 0,
            "max_reflections": 2,
            "is_safe": False,
            "violations": [],
            "waypoints": [],
            "logs": [],
            "extraction_accuracy": 0.0,
        }

    def test_01_single_flood_hazard_extraction(self):
        """Kiểm thử 1: Trích xuất 1 điểm ngập cụ thể kèm độ sâu và khung giờ."""
        news = (
            "Chiều 19-10 vào lúc 17h30, triều cường rằm tháng 9 dâng cao lịch sử "
            "khiến tuyến đường Trần Xuân Soạn thuộc Quận 7 ngập sâu hơn 45cm, "
            "nhiều phương tiện xe máy bị chết máy hàng loạt."
        )
        self.base_state["news_context"] = news

        result = traffic_perception_agent(self.base_state)

        # Kiểm tra kết quả trích xuất
        hazards = result["avoid_points"]
        self.assertGreater(len(hazards), 0, "Phải trích xuất được ít nhất 1 điểm ngập.")
        
        # Tìm điểm Trần Xuân Soạn
        txs = next((h for h in hazards if "trần xuân soạn" in h["street"].lower()), None)
        self.assertIsNotNone(txs, "Không tìm thấy đường Trần Xuân Soạn trong kết quả.")
        
        # Kiểm tra tọa độ không gian hợp lệ tại TP.HCM (vĩ độ ~10.x, kinh độ ~106.x)
        self.assertAlmostEqual(txs["lat"], 10.75, delta=0.05)
        self.assertAlmostEqual(txs["lon"], 106.70, delta=0.05)
        self.assertGreater(txs["radius_m"], 0.0)

        # Kiểm tra độ chính xác bóc tách
        self.assertEqual(result["extraction_accuracy"], 1.0)
        print("\n[Test 1 PASS] Trích xuất thành công Trần Xuân Soạn:", txs)

    def test_02_multiple_flood_hazards_extraction(self):
        """Kiểm thử 2: Trích xuất đồng thời nhiều điểm ngập ở các quận khác nhau."""
        news = (
            "Cơn mưa lớn kéo dài chiều nay khiến đường Quốc Hương tại phường Thảo Điền (TP Thủ Đức) "
            "ngập nửa bánh xe. Cùng lúc đó, khu vực dốc đường Võ Văn Ngân chợ Thủ Đức nước chảy xiết."
        )
        self.base_state["news_context"] = news

        result = traffic_perception_agent(self.base_state)
        hazards = result["avoid_points"]

        self.assertGreaterEqual(len(hazards), 2, "Phải trích xuất được cả 2 tuyến đường ngập.")

        street_names = [h["street"].lower() for h in hazards]
        self.assertTrue(any("quốc hương" in s for s in street_names), "Thiếu đường Quốc Hương.")
        self.assertTrue(any("võ văn ngân" in s for s in street_names), "Thiếu đường Võ Văn Ngân.")
        print(f"\n[Test 2 PASS] Trích xuất thành công {len(hazards)} điểm ngập: {street_names}")

    def test_03_negative_case_normal_traffic(self):
        """Kiểm thử 3: Bản tin bình thường không ngập lụt -> Không được ảo giác tạo điểm cấm."""
        news = (
            "Sáng nay thời tiết tại trung tâm TP.HCM nắng đẹp, giao thông trên đường "
            "Lê Lợi và đường Nguyễn Huệ thông thoáng, các phương tiện di chuyển thuận lợi."
        )
        self.base_state["news_context"] = news

        result = traffic_perception_agent(self.base_state)
        hazards = result["avoid_points"]

        self.assertEqual(len(hazards), 0, "Không được tự ý tạo điểm cấm khi đường không ngập.")
        self.assertEqual(result["extraction_accuracy"], 0.0)
        print("\n[Test 3 PASS] Nhận diện chính xác bản tin không ngập lụt (0 hazards).")

    def test_04_gazetteer_fallback_mechanism(self):
        """Kiểm thử 4: Kiểm tra cơ chế Fallback từ điển địa danh khi không dùng LLM."""
        from app.core.settings import settings
        original_key = settings.GOOGLE_API_KEY

        try:
            # Tạm thời gỡ API key để ép hệ thống rơi vào luồng Fallback Rule-based
            settings.GOOGLE_API_KEY = ""
            news = "Mưa xối xả làm ngập đường Nguyễn Hữu Cảnh và đường Ung Văn Khiêm tại Bình Thạnh."
            self.base_state["news_context"] = news

            result = traffic_perception_agent(self.base_state)
            hazards = result["avoid_points"]

            self.assertGreater(len(hazards), 0, "Cơ chế Fallback Gazetteer phải nhận diện được tên đường quen thuộc.")
            
            # Kiểm tra xem có log [Gazetteer Fallback] hay không
            fallback_logs = [log for log in result["logs"] if "Gazetteer Fallback" in log]
            self.assertGreater(len(fallback_logs), 0, "Phải ghi nhận log luồng Fallback.")
            print(f"\n[Test 4 PASS] Luồng Fallback hoạt động xuất sắc khi không có LLM: {len(hazards)} điểm ngập.")
        finally:
            # Khôi phục lại key
            settings.GOOGLE_API_KEY = original_key

    def test_05_geocoding_service_integration(self):
        """Kiểm thử 5: Kiểm tra trực tiếp dịch vụ Geocoding (Local Dataset & Contextual Query)."""
        # 1. Tra cứu điểm có trong danh bạ đen chuẩn hóa
        geo_txs = geocode_street("Trần Xuân Soạn", district="Quận 7")
        self.assertIsNotNone(geo_txs)
        self.assertEqual(geo_txs["street"], "Trần Xuân Soạn")
        self.assertAlmostEqual(geo_txs["lat"], 10.7523, delta=0.01)

        # 2. Tra cứu điểm có thông tin phường
        geo_qh = geocode_street("Quốc Hương", ward="Thảo Điền", district="TP Thủ Đức")
        self.assertIsNotNone(geo_qh)
        self.assertEqual(geo_qh["street"], "Quốc Hương")

        print("\n[Test 5 PASS] Dịch vụ Geocoding phản hồi tọa độ chuẩn xác.")

    def test_06_colloquial_social_media_extraction(self):
        """Kiểm thử 6: Trích xuất bản tin từ mạng xã hội với văn phong đời thường, ngôn ngữ tự nhiên."""
        news = (
            "Cảnh báo ngập: Đoạn đường Nguyễn Văn Quá ở Quận 12 nước tràn lút nửa bánh xe "
            "vào lúc 18h tối nay do mưa to dầm dề, bà con đi làm về chú ý tìm đường khác nhé!"
        )
        self.base_state["news_context"] = news

        result = traffic_perception_agent(self.base_state)
        hazards = result["avoid_points"]

        self.assertGreater(len(hazards), 0, "Phải nhận diện được điểm ngập từ bài đăng mạng xã hội.")
        nvq = next((h for h in hazards if "nguyễn văn quá" in h["street"].lower()), None)
        self.assertIsNotNone(nvq, "Không tìm thấy đường Nguyễn Văn Quá.")
        self.assertAlmostEqual(nvq["lat"], 10.84, delta=0.05)
        print(f"\n[Test 6 PASS] Trích xuất thành công văn phong mạng xã hội: {nvq['street']} ({nvq['severity']})")

    def test_07_llm_api_exception_fallback(self):
        """Kiểm thử 7: Giả lập lỗi API LLM (Network Timeout / Quota) -> Hệ thống tự động fallback êm thấm."""
        from unittest.mock import patch
        
        news = "Đường Ung Văn Khiêm ngập sâu khiến hàng loạt xe cộ không thể di chuyển."
        self.base_state["news_context"] = news

        # Giả lập lỗi ném ra từ invoke của LLM
        with patch("app.agents.perception.ChatGoogleGenerativeAI.with_structured_output") as mock_extractor:
            mock_extractor.side_effect = RuntimeError("Mocked 503 Service Unavailable / Quota Exceeded")
            
            result = traffic_perception_agent(self.base_state)
            hazards = result["avoid_points"]

            # Phải có điểm ngập được trích xuất thông qua Fallback Gazetteer
            self.assertGreater(len(hazards), 0, "Hệ thống phải tự động fallback sang Gazetteer khi LLM gặp sự cố.")
            self.assertTrue(any("ung văn khiêm" in h["street"].lower() for h in hazards))
            
            # Kiểm tra log có ghi nhận ngoại lệ và fallback
            error_logs = [log for log in result["logs"] if "Gemini LLM extraction error" in log]
            self.assertGreater(len(error_logs), 0, "Phải ghi nhận log lỗi ngoại lệ của LLM.")
            print("\n[Test 7 PASS] Khả năng chịu lỗi (Fault-Tolerance) hoạt động hoàn hảo khi LLM gặp sự cố.")

    def test_08_empty_or_whitespace_news(self):
        """Kiểm thử 8: Xử lý an toàn khi bản tin trống hoặc chỉ chứa khoảng trắng."""
        self.base_state["news_context"] = "   \n\t  "
        result = traffic_perception_agent(self.base_state)

        self.assertEqual(len(result["avoid_points"]), 0)
        self.assertEqual(result["extraction_accuracy"], 0.0)
        print("\n[Test 8 PASS] Xử lý an toàn với đầu vào trống rỗng.")


if __name__ == "__main__":
    unittest.main(verbosity=2)
