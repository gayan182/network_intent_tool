import shutil

def generate_intended():
    shutil.copy("current/bgp.yaml", "intended/state.yaml")
    print("Intended state saved to intended/state.yaml")

    


if __name__ == "__main__":
    generate_intended()


