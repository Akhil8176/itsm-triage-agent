import multiprocessing
import time

DURATION_SECONDS = 60


def burn_cpu(seconds):
    end_time = time.time() + seconds
    n = 0
    while time.time() < end_time:
        for _ in range(100_000):
            n = (n * 31 + 7) % 1_000_003


if __name__ == "__main__":
    cores = multiprocessing.cpu_count()
    print(f"Stressing CPU on all {cores} cores for {DURATION_SECONDS} seconds...")
    processes = [multiprocessing.Process(target=burn_cpu, args=(DURATION_SECONDS,)) for _ in range(cores)]
    for p in processes:
        p.start()
    for p in processes:
        p.join()
    print("Done.")
