import time
import multiprocessing

def burn_cpu():
    end_time = time.time() + 20
    while time.time() < end_time:
        x = 99999999 ** 2

if __name__ == "__main__":
    print("Stressing CPU for 20 seconds across multiple cores...")
    processes = []
    for _ in range(multiprocessing.cpu_count()):
        p = multiprocessing.Process(target=burn_cpu)
        p.start()
        processes.append(p)
    for p in processes:
        p.join()
    print("Done.")