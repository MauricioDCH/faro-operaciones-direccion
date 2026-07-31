import unittest

from faro import __version__
from faro.main import get_status


class PackageTests(unittest.TestCase):
    def test_package_version_is_defined(self) -> None:
        self.assertEqual(__version__, "0.1.0")

    def test_scaffold_status_is_explicit(self) -> None:
        self.assertEqual(
            get_status(),
            {
                "application": "Faro",
                "version": "0.1.0",
                "status": "repository-scaffold",
            },
        )


if __name__ == "__main__":
    unittest.main()
