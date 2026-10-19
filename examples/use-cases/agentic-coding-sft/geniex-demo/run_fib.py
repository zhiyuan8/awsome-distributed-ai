import os, random, runpy, sys
random.seed(7)
src = os.path.abspath(os.path.join(os.path.dirname(__file__) or ".", "..", "src"))
sys.path.insert(0, src)
sys.argv = ["compare.py", "--backend", "geniex", "--mode", "inject",
            "--tasks", "../tasks_root", "--out", "../compare_out/demo_fib"]
runpy.run_path(os.path.join(src, "compare.py"), run_name="__main__")
