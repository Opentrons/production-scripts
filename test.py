G_A = {}


def add_a():
    G_A = {'1': 1}
    return G_A


def run():
    for i in range(10):
        add_a()


if __name__ == '__main__':
    G_A['1'] = 2
    run()
    print(G_A)
