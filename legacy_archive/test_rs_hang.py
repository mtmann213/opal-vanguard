from src.rs_helper import RS1511
import time

def test_hang():
    rs = RS1511()
    # A valid message
    data = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]
    msg = rs.encode(data)
    
    # Introduce 2 errors - this should trigger the 2-symbol brute force
    corrupted = list(msg)
    corrupted[0] ^= 1
    corrupted[1] ^= 1
    
    print("Starting 2-error decode (brute force)...")
    start = time.time()
    result = rs.decode(corrupted)
    end = time.time()
    print(f"Done in {end - start:.4f} seconds.")
    
    # Introduce 3 errors - this will exhaust the 2-symbol brute force and return
    corrupted_3 = list(msg)
    corrupted_3[0] ^= 1
    corrupted_3[1] ^= 1
    corrupted_3[2] ^= 1
    
    print("Starting 3-error decode (exhaustive brute force)...")
    start = time.time()
    result = rs.decode(corrupted_3)
    end = time.time()
    print(f"Done in {end - start:.4f} seconds.")

if __name__ == '__main__':
    test_hang()
