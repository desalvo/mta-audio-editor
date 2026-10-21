"""Seed-VC offline CLI with complete active checkpoint validation."""
from studio_offline_runner import main

if __name__=='__main__':
    main(checkpoint_guard=True)
