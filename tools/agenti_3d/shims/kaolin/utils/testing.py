"""FlexiCubes di TRELLIS importa solo questo controllo da kaolin: il pacchetto
completo non ha ruote per torch cu128 su Windows."""


def check_tensor(tensor, shape=None, dtype=None, device=None, throw=True):
    return True
