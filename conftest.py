# Root pytest configuration.
#
# The ad-hoc scripts src/python/test_*.py are exploratory developer tools that
# require a live server and Copilot authentication (they import the `copilot`
# SDK at module load). They are NOT unit tests and must not be collected by CI.
#
# This glob ignores only those top-level scripts. Real unit tests placed under
# src/python/tests/ (e.g. src/python/tests/test_foo.py) are still collected,
# because their path does not match "src/python/test_*.py".
collect_ignore_glob = ["src/python/test_*.py"]
