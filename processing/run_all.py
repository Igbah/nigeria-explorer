"""Run the whole processing pipeline in order: raw_data/ -> processed/ -> data/ (what the web page reads).

Usage (from the project folder):
    python processing/run_all.py            # all steps
    python processing/run_all.py 5 6        # only steps 5 and 6 (e.g. after adding age/sex files)
"""
import subprocess, sys, time, os

STEPS = {
    1: "step1_state_indicators.py",   # state boundaries, poverty, maternal mortality, contraception, bribery, displacement, CRSV
    2: "step2_health_facilities.py",  # health facilities: level, type, indicative ownership, location checks
    3: "step3_population.py",         # GRID3 100 m population -> state totals, H3 hexagons, 1 km summary raster
    4: "step4_lgas.py",               # LGA boundaries -> LGA population, facilities, displacement
    5: "step5_age_sex.py",            # WorldPop 1 km age/sex shares -> pyramids for states, LGAs, hexagons
    6: "step6_build_web_data.py",     # pack everything into data/ for index.html
}
here = os.path.dirname(os.path.abspath(__file__))
todo = [int(a) for a in sys.argv[1:]] or list(STEPS)
for n in todo:
    t = time.time()
    print(f"\n=== Step {n}: {STEPS[n]} ===", flush=True)
    r = subprocess.run([sys.executable, os.path.join(here, STEPS[n])])
    if r.returncode:
        sys.exit(f"Step {n} failed (exit code {r.returncode}). Fix the message above and re-run: python processing/run_all.py {n}")
    print(f"Step {n} finished in {time.time() - t:.0f} s")
print("\nAll done. Open index.html through a local server (see README.md).")
