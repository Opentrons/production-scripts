G_A = {"1": 1}


def add_a(G_A: dict):
    G_A['1'] = G_A['1'] + 1


def run():
    for i in range(10):
        add_a(G_A)


if __name__ == '__main__':
    run()
    print(G_A)
