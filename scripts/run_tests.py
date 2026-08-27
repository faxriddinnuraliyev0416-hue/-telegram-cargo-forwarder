"""
32 ta xabar va aloqa testlarini ishga tushirish hamda chiroyli hisobot chiqarish skripti.
Foydalanish:
    python -m scripts.run_tests
"""
import sys
import unittest
from tests.test_cargo_suite import TestCargoSuite


def run_all_tests():
    print("=" * 65)
    print("[TESTS] TELEGRAM CARGO FORWARDER - 32 TA XABAR VA TIZIM SINOVLARI")
    print("=" * 65)

    suite = unittest.TestLoader().loadTestsFromTestCase(TestCargoSuite)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    print("\n" + "=" * 65)
    print(f"Jami testlar: {result.testsRun}")
    print(f"Muvaffaqiyatli: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"Xatolar: {len(result.errors)}")
    print(f"Muvaffaqiyatsiz: {len(result.failures)}")
    print("=" * 65)

    if result.wasSuccessful():
        print("[SUCCESS] BARCHA 32 TA XABAR VA ALOQA SINOVLARI 100% MUVAFFAQIYATLI O'TDI!")
        return 0
    else:
        print("[FAIL] Ba'zi testlarda xatolik aniqlandi.")
        return 1


if __name__ == "__main__":
    sys.exit(run_all_tests())

