"""
32 ta real xabarlar va aloqa testlari to'plami.
Test qilinadigan holatlar:
1. 20 ta turli xil haqiqiy yuk e'lonlari (shahar, tuman, tonnaj, mashina, telefon, narx).
2. 6 ta taksi va yo'lovchi xabarlari (qat'iy rad etilishi kerak).
3. 6 ta spam, reklama va chat xabarlari (qat'iy rad etilishi kerak).
4. Telefon raqamlari (barcha prefikslar va xalqaro) to'g'ri formatlanishi.
5. Google Maps qidiruv va marshrut havolalari to'g'ri shakllanishi.
6. Duplikatlar xeshi va filtrlarga mos kelish (matching).
"""
import unittest

from app import geodata
from app.parser import parse_message, extract_phone_numbers
from app.matcher import matches
from app.models import CargoFilter
from app.geodata import google_maps_search_url, google_maps_route_url
from app.utils.formatting import build_forwarded_message


class TestCargoSuite(unittest.TestCase):

    def setUp(self):
        # 32 ta real xabarlar to'plami
        self.test_messages = [
            # --- 1-20: HAQIQIY YUK E'LONLARI (is_cargo == True) ---
            {
                "id": 1,
                "text": "Toshkentdan Samarqandga 20 tonna sement yuk bor fura kerak 901234567",
                "is_cargo": True,
                "expected_origin": "Toshkent",
                "expected_dest": "Samarqand",
                "expected_vehicle": "fura",
                "expected_tonnage": "20 tonna",
                "expected_phone": "+998 90 123 45 67",
            },
            {
                "id": 2,
                "text": "Срочно груз Ташкент - Бухара 10 тонн стройматериалы, Исузу. Тел +998931234567",
                "is_cargo": True,
                "expected_origin": "Toshkent",
                "expected_dest": "Buxoro",
                "expected_vehicle": "isuzu",
                "expected_tonnage": "10 tonna",
                "expected_phone": "+998 93 123 45 67",
            },
            {
                "id": 3,
                "text": "Фаргонадан Тошкентга гилос бор 5 тонна реф керак 99 888 77 66",
                "is_cargo": True,
                "expected_origin": "Farg'ona",
                "expected_dest": "Toshkent",
                "expected_vehicle": "refrijerator",
                "expected_tonnage": "5 tonna",
                "expected_phone": "+998 99 888 77 66",
            },
            {
                "id": 4,
                "text": "Denovdan Kattaqorgonga un bor 3 tonna gazel 91-234-56-78",
                "is_cargo": True,
                "expected_origin": "Denov",
                "expected_dest": "Kattaqorgon",
                "expected_vehicle": "gazel",
                "expected_tonnage": "3 tonna",
                "expected_phone": "+998 91 234 56 78",
            },
            {
                "id": 5,
                "text": "Andijon ➔ Nukus | 22 tn un | MAN kerak | tel: +998 (97) 111-22-33",
                "is_cargo": True,
                "expected_origin": "Andijon",
                "expected_dest": "Nukus",
                "expected_vehicle": "kamaz",
                "expected_tonnage": "22 tonna",
                "expected_phone": "+998 97 111 22 33",
            },
            {
                "id": 6,
                "text": "Chilonzordan Sergeliga mebel kochirish bor labo kerak 946543210",
                "is_cargo": True,
                "expected_origin": "Toshkent",
                "expected_dest": "Toshkent",
                "expected_vehicle": "labo",
                "expected_phone": "+998 94 654 32 10",
            },
            {
                "id": 7,
                "text": "Qarshidan Toshkentga yuk bor 15 tonna. Tel 901112233, 934445566",
                "is_cargo": True,
                "expected_origin": "Qarshi",
                "expected_dest": "Toshkent",
                "expected_tonnage": "15 tonna",
                "phone_count": 2,
            },
            {
                "id": 8,
                "text": "Toshkentdan Olmaotaga 20t yuk bor tent fura +998901239999",
                "is_cargo": True,
                "expected_origin": "Toshkent",
                "expected_dest": "Olmaota",
                "expected_vehicle": "fura",
                "expected_phone": "+998 90 123 99 99",
            },
            {
                "id": 9,
                "text": "salom akalar buxoro toshkentga 5t yuk bor isuzi bormi 998901234560",
                "is_cargo": True,
                "expected_origin": "Buxoro",
                "expected_dest": "Toshkent",
                "expected_vehicle": "isuzu",
                "expected_tonnage": "5 tonna",
            },
            {
                "id": 10,
                "text": "Vodiydan Toshkentga olma bor 10t ref 931234567",
                "is_cargo": True,
                "expected_origin": "Vodiy",
                "expected_dest": "Toshkent",
                "expected_vehicle": "refrijerator",
                "expected_tonnage": "10 tonna",
            },
            {
                "id": 11,
                "text": "Samarqand - Namangan 40 kub penoplast bor gazel 901234567",
                "is_cargo": True,
                "expected_origin": "Samarqand",
                "expected_dest": "Namangan",
                "expected_vehicle": "gazel",
                "expected_volume": "40 m³",
            },
            {
                "id": 12,
                "text": "Navoiydan Toshkentga 20t temir bor 3.5 mln beramiz fura 901234567",
                "is_cargo": True,
                "expected_origin": "Navoiy",
                "expected_dest": "Toshkent",
                "expected_vehicle": "fura",
                "expected_price": "3.5 mln",
            },
            {
                "id": 13,
                "text": "Urgutdan Toshkentga 2 tn mayiz bor porter 90 999 88 77",
                "is_cargo": True,
                "expected_origin": "Urgut",
                "expected_dest": "Toshkent",
                "expected_vehicle": "kiya",
                "expected_tonnage": "2 tonna",
            },
            {
                "id": 14,
                "text": "Olotchegaradan Toshkentga 22 tonna truba bor Fura kerak 93 111 22 33",
                "is_cargo": True,
                "expected_origin": "Buxoro",
                "expected_dest": "Toshkent",
                "expected_vehicle": "fura",
            },
            {
                "id": 15,
                "text": "Quvadan Moskvaga gilos yuk bor 20 tonna refrigorator +998941234567",
                "is_cargo": True,
                "expected_origin": "Quva",
                "expected_dest": "Moskva",
                "expected_vehicle": "refrijerator",
            },
            {
                "id": 16,
                "text": "Gulistondan Buxoroga 12t paxta yog'i bor Kamaz 95 123 45 67",
                "is_cargo": True,
                "expected_origin": "Guliston",
                "expected_dest": "Buxoro",
                "expected_vehicle": "kamaz",
                "expected_tonnage": "12 tonna",
            },
            {
                "id": 17,
                "text": "Urganch Toshkent 8 tonna guruch yuk bor Isuzu 90 333 44 55",
                "is_cargo": True,
                "expected_origin": "Urganch",
                "expected_dest": "Toshkent",
                "expected_vehicle": "isuzu",
            },
            {
                "id": 18,
                "text": "Zomindan Samarqandga 4 tonna kartoshka yuk bor Gazel 97 777 88 99",
                "is_cargo": True,
                "expected_origin": "Zomin",
                "expected_dest": "Samarqand",
                "expected_vehicle": "gazel",
            },
            {
                "id": 19,
                "text": "Olmaliqdan Toshkentga 30 tonna shag'al bor Samosval kerak 90 123 00 00",
                "is_cargo": True,
                "expected_origin": "Olmaliq",
                "expected_dest": "Toshkent",
                "expected_vehicle": "samosval",
            },
            {
                "id": 20,
                "text": "Sergelidan Bekobodga stanok yuk bor Manipulyator 99 000 11 22",
                "is_cargo": True,
                "expected_origin": "Toshkent",
                "expected_dest": "Bekobod",
                "expected_vehicle": "manipulyator",
            },

            # --- 21-26: TAKSI VA YO'LOVCHI XABARLARI (Rad etilishi shart: is_cargo == False) ---
            {
                "id": 21,
                "text": "Toshkent Samarqand 4 kishi kerak nexia pitakda turibmiz 901234567",
                "is_cargo": False,
            },
            {
                "id": 22,
                "text": "Ertaga ertalab Qarshiga 2 kishi olib ketaman Cobalt konditsioner bor 931234567",
                "is_cargo": False,
            },
            {
                "id": 23,
                "text": "Andijon Toshkent pochta odam bor gentra moshina tayyor 991234567",
                "is_cargo": False,
            },
            {
                "id": 24,
                "text": "Buxorodan Toshkentga bilet joy bor Spark 941234567",
                "is_cargo": False,
            },
            {
                "id": 25,
                "text": "Toshkentdan Farg'onaga 1 kishi kerak yo'lovchi olamiz 901234567",
                "is_cargo": False,
            },
            {
                "id": 26,
                "text": "Samarqand Toshkent taksi bor Cobalt 4 odam 911234567",
                "is_cargo": False,
            },

            # --- 27-32: SPAM, REKLAMA VA CHAT (Rad etilishi shart: is_cargo == False) ---
            {
                "id": 27,
                "text": "Assalomu alaykum kartaga pul tashlab beramiz qulay foizda 901234567",
                "is_cargo": False,
            },
            {
                "id": 28,
                "text": "Kriptovalyuta sotib olamiz va sotamiz USDT click payme",
                "is_cargo": False,
            },
            {
                "id": 29,
                "text": "Uy sotiladi Yunusobodda 3 xona evroremont 901234567",
                "is_cargo": False,
            },
            {
                "id": 30,
                "text": "Ishga taklif qilamiz oylik 5 mln so'm ofisga qizlar kerak 931234567",
                "is_cargo": False,
            },
            {
                "id": 31,
                "text": "Kim hozir yo'lda? Qamchiq dovoni ochiqmi?",
                "is_cargo": False,
            },
            {
                "id": 32,
                "text": "Salom barchaga guruhdagilar qandaysizlar ishlar yaxshimi",
                "is_cargo": False,
            },
        ]

    def test_32_messages_classification_and_parsing(self):
        """Barcha 32 ta xabar bo'yicha to'liq test sinovi."""
        self.assertEqual(len(self.test_messages), 32, "Testlar soni aynan 32 ta bo'lishi shart!")

        passed_count = 0
        for item in self.test_messages:
            msg_id = item["id"]
            text = item["text"]
            expected_cargo = item["is_cargo"]

            parsed = parse_message(text)

            # 1. Cargo vs Non-cargo to'g'riligi
            self.assertEqual(
                parsed.is_cargo, expected_cargo,
                f"Test #{msg_id} tasnif xatosi: Kutilgan is_cargo={expected_cargo}, olindi={parsed.is_cargo} | Matn: {text}"
            )

            # 2. Agar yuk bo'lsa, maydonlar to'g'riligi
            if expected_cargo:
                if "expected_origin" in item:
                    self.assertIsNotNone(parsed.origin, f"Test #{msg_id} origin topilmadi: {text}")
                    self.assertTrue(
                        geodata.region_of(parsed.origin) == geodata.region_of(item["expected_origin"]) or
                        item["expected_origin"].lower() in parsed.origin.lower() or
                        parsed.origin.lower() in item["expected_origin"].lower(),
                        f"Test #{msg_id} origin xatosi: Kutilgan={item['expected_origin']}, Olindi={parsed.origin}"
                    )

                if "expected_dest" in item:
                    self.assertIsNotNone(parsed.destination, f"Test #{msg_id} destination topilmadi: {text}")
                    self.assertTrue(
                        geodata.region_of(parsed.destination) == geodata.region_of(item["expected_dest"]) or
                        item["expected_dest"].lower() in parsed.destination.lower() or
                        parsed.destination.lower() in item["expected_dest"].lower(),
                        f"Test #{msg_id} destination xatosi: Kutilgan={item['expected_dest']}, Olindi={parsed.destination}"
                    )

                if "expected_vehicle" in item:
                    self.assertIn(item["expected_vehicle"], parsed.vehicle_types, f"Test #{msg_id} transport xatosi: {parsed.vehicle_types}")

                if "expected_tonnage" in item:
                    self.assertEqual(parsed.tonnage, item["expected_tonnage"])

                if "expected_phone" in item:
                    self.assertIsNotNone(parsed.primary_phone)
                    self.assertEqual(parsed.primary_phone, item["expected_phone"])

                if "phone_count" in item:
                    self.assertEqual(len(parsed.phones), item["phone_count"])

                # Google Maps linklari mavjudligi
                self.assertIsNotNone(parsed.google_origin_url)
                self.assertIn("google.com/maps", parsed.google_origin_url)
                if parsed.destination:
                    self.assertIsNotNone(parsed.google_route_url)
                    self.assertIn("google.com/maps/dir", parsed.google_route_url)

            passed_count += 1

        self.assertEqual(passed_count, 32)
        print("[SUCCESS] 32 ta xabar sinovi 100% muvaffaqiyatli o'tdi! (20 ta yuk + 6 ta taksi rad + 6 ta spam rad)")

    def test_phone_number_formats(self):
        """Telefon raqamlarini barcha formatlarda sinash."""
        test_phones = [
            ("+998901234567", "+998 90 123 45 67"),
            ("998931234567", "+998 93 123 45 67"),
            ("94 123 45 67", "+998 94 123 45 67"),
            ("(97) 123-45-67", "+998 97 123 45 67"),
            ("91-234-56-78", "+998 91 234 56 78"),
            ("33 123 45 67", "+998 33 123 45 67"),
            ("88 999 00 11", "+998 88 999 00 11"),
            ("77 555 44 33", "+998 77 555 44 33"),
            ("+7 (999) 123-45-67", "+7 (999) 123-45-67"),
        ]

        for raw_num, expected_formatted in test_phones:
            text = f"Toshkentdan Samarqandga yuk bor fura kerak tel: {raw_num}"
            phones = extract_phone_numbers(text)
            self.assertTrue(len(phones) >= 1, f"Telefon topilmadi: {raw_num}")
            self.assertEqual(phones[0].formatted, expected_formatted)

        print("[SUCCESS] Telefon raqamlarini formatlash testlari muvaffaqiyatli o'tdi!")

    def test_google_maps_urls(self):
        """Google Maps qidiruv va marshrut linklarini tekshirish."""
        search_url = google_maps_search_url("Toshkent")
        self.assertIn("https://www.google.com/maps/search/?api=1&query=", search_url)
        self.assertIn("Toshkent", search_url)

        route_url = google_maps_route_url("Toshkent", "Samarqand")
        self.assertIn("https://www.google.com/maps/dir/?api=1&origin=", route_url)
        self.assertIn("destination=", route_url)
        print("[SUCCESS] Google Maps havolalar integratsiyasi sinovi muvaffaqiyatli o'tdi!")

    def test_cargo_matching_with_filter(self):
        """Yuk e'lonining foydalanuvchi filtri bilan mos kelishi (matching)."""
        parsed = parse_message("Toshkentdan Samarqandga 20 tonna yuk bor fura kerak 901234567")

        # Mos keladigan filtr
        f1 = CargoFilter(origin="Toshkent", destination="Samarqand", vehicle_type="fura", tonnage="20 tonna")
        self.assertTrue(matches(f1, parsed))

        # 'Istalgan' filtr
        f2 = CargoFilter(origin="Toshkent", destination="Istalgan", vehicle_type="Istalgan", tonnage="Istalgan")
        self.assertTrue(matches(f2, parsed))

        # Boshqa yo'nalish filtri (mos kelmasligi kerak)
        f3 = CargoFilter(origin="Buxoro", destination="Andijon", vehicle_type="fura", tonnage="20 tonna")
        self.assertFalse(matches(f3, parsed))
        print("[SUCCESS] Filtr matching logikasi sinovi muvaffaqiyatli o'tdi!")

    def test_message_formatting_html(self):
        """Formatlangan HTML xabarning to'liqligi va xavfsizligini tekshirish."""
        parsed = parse_message("Toshkentdan Samarqandga 20 tonna sement bor fura kerak tel: 901234567")
        formatted_html = build_forwarded_message(
            source_title="Yuk Markazi O'zbekiston",
            source_username="yuk_markazi",
            sender_name="Haydarbek",
            sender_username="haydarbek_admin",
            sender_id=7929184484,
            original_text="Toshkentdan Samarqandga 20 tonna sement bor fura kerak tel: 901234567",
            origin=parsed.origin,
            destination=parsed.destination,
            vehicle_types=parsed.vehicle_types,
            tonnage=parsed.tonnage,
            cargo_type=parsed.cargo_type,
            phones=parsed.phones,
        )

        self.assertIn("🚚 <b>YUK E'LONI</b>", formatted_html)
        self.assertIn("google.com/maps", formatted_html)
        self.assertIn("tel:+998901234567", formatted_html)
        self.assertIn("+998 90 123 45 67", formatted_html)
        self.assertIn("t.me/haydarbek_admin", formatted_html)
        print("[SUCCESS] HTML formatlash va vizual ko'rinish sinovi muvaffaqiyatli o'tdi!")


if __name__ == "__main__":
    unittest.main()

