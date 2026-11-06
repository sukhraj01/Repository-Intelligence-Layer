"""Executable evaluation of patches on SWE-bench Verified instances without root or a container.

Implements ``docs/RQ3_PILOT.md`` ("Can resolved rate be measured on the cluster?") and the
decision recorded as D106: one function builds an instance environment with ``uv``, applies a
patch, runs the named tests and returns per-test outcomes. Lead-owned; workstream C's
``ril/agent`` modules are not touched.
"""
