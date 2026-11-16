"""Export the real nycflights13 dataset (US Bureau of Transportation Statistics, all 2013 flights out of
EWR, JFK, LGA) to CSV so the Spark pipeline reads it like any other raw source."""
import os
import nycflights13 as n
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "flights_raw")
def export(out=OUT):
    os.makedirs(out, exist_ok=True)
    for name in ["flights", "airlines", "airports", "planes", "weather"]:
        getattr(n, name).to_csv(os.path.join(out, f"{name}.csv"), index=False)
    return out
if __name__ == "__main__": print("wrote", export())
