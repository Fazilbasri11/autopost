import json
import unittest
from unittest.mock import MagicMock, patch

import main


class TestAutopostLogic(unittest.TestCase):
    def test_pick_product_prefers_lowest_total_post(self):
        products = [
            {"row_number": 2, "Produk": "A", "Total_Post": 3},
            {"row_number": 3, "Produk": "B", "Total_Post": ""},
            {"row_number": 4, "Produk": "C", "Total_Post": 1},
        ]
        chosen = main.pick_product(products)
        self.assertEqual(chosen["Produk"], "B")

    def test_pick_angle_avoids_repeating_last_angle(self):
        first_label = main.ANGLES[0].split(":")[0]
        for _ in range(15):
            chosen = main.pick_angle(first_label)
            self.assertNotEqual(chosen.split(":")[0], first_label)

    @patch("main.requests.post")
    def test_generate_thread_posts_enforces_link_and_char_limit(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.json.return_value = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "text": json.dumps(
                                    {
                                        "posts": [
                                            "Tips lolos tes " + ("x" * 600) + "\ufffc",
                                            "Lo lagi di fase mana?",
                                            "Tip 1: fokus belajar",
                                            "Tip 2: rangkum tulisan tangan",
                                            "Tip 3: latihan tiap hari",
                                            "Gue pakai 2 buku ini. Kekurangannya: butuh paham konsep.",
                                            "Ini link bukunya, kalau udah punya pakai aja.",
                                            "Ada pertanyaan? Tanya di komen, gue jawab satu-satu.",
                                        ]
                                    }
                                )
                            }
                        ]
                    }
                }
            ]
        }
        mock_post.return_value = mock_resp

        posts = main.generate_thread_posts(
            "fake-key",
            "gemini-2.5-flash",
            {
                "Produk": "Buku Sang Tutor & Al Faiz",
                "Keunggulan": "Trik cepat TIU & all rounded",
                "Kekurangan": "Tetap butuh paham konsep dasar",
                "Link_Produk": "https://example.com/produk-1\nhttps://example.com/produk-2",
            },
            main.ANGLES[0],
        )

        self.assertEqual(len(posts), 8)
        for post in posts:
            self.assertLessEqual(len(post), main.MAX_THREADS_CHARS)
            self.assertNotIn("\ufffc", post)
        self.assertIn("https://example.com/produk-1", posts[-2])
        self.assertIn("https://example.com/produk-2", posts[-2])
        self.assertNotIn("https://example.com/", posts[-1])

    @patch("main.time.sleep", return_value=None)
    @patch("main.create_and_publish_single")
    def test_publish_thread_chain_links_reply_to_id(self, mock_pub, _mock_sleep):
        mock_pub.side_effect = ["id_1", "id_2", "id_3"]
        ids = main.publish_thread_chain(
            user_id="user_99",
            access_token="tok",
            posts=["p1", "p2", "p3"],
            image_url="https://example.com/pic.jpg",
            dry_run=False,
        )
        self.assertEqual(ids, ["id_1", "id_2", "id_3"])
        self.assertEqual(
            mock_pub.call_args_list[0].kwargs,
            {
                "user_id": "user_99",
                "access_token": "tok",
                "text": "p1",
                "reply_to_id": None,
                "image_url": "https://example.com/pic.jpg",
            },
        )
        self.assertEqual(mock_pub.call_args_list[1].kwargs["reply_to_id"], "id_1")
        self.assertIsNone(mock_pub.call_args_list[1].kwargs["image_url"])
        self.assertEqual(mock_pub.call_args_list[2].kwargs["reply_to_id"], "id_2")


if __name__ == "__main__":
    unittest.main()
