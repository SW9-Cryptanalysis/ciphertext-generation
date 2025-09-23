from decimal import Decimal


def extract_homophones(cipher_symbols):
    ideal_homophones: list[Decimal] = [
        cipher_symbols * (freq / 100) for freq in frequencies.values()
    ]
    homophones_dict: dict[str, int] = dict(
        zip(frequencies.keys(), add_noise(ideal_homophones))
    )
    homophones_dict = adjust_homophones(cipher_symbols, homophones_dict)

    return homophones_dict


def adjust_homophones(cipher_symbols, homophones_dict) -> dict[str, int]:
    """Adjust the homophone counts to ensure the total matches the desired number of cipher symbols."""
    import random

    while sum(homophones_dict.values()) > cipher_symbols:
        letter = random.choice(
            list(filter(lambda k: homophones_dict[k] > 1, homophones_dict.keys()))
        )
        if homophones_dict[letter] > 1:
            homophones_dict[letter] -= 1

    while sum(homophones_dict.values()) < cipher_symbols:
        letter = random.choice(
            list(filter(lambda k: homophones_dict[k] > 1, homophones_dict.keys()))
        )
        homophones_dict[letter] += 1
    return homophones_dict


def add_noise(ideal_homophones: list[Decimal], k: int = 2) -> list[int]:
    """Add random noise to the ideal homophone counts to create variability.

    Noise is added by a uniform random integer value between -k and k

    Args:
            ideal_homophones (list[Decimal]): List of ideal homophone counts for each letter.

    Returns:
            list[int]: List of rounded homophone counts with added noise.
    """

    import random

    noisy_homophones: list[int] = []
    for count in ideal_homophones:
        noise = random.randint(-k, k)
        noisy_count = max(1, count + noise)  # Ensure at least one homophone
        noisy_homophones.append(round(noisy_count))
    return noisy_homophones


frequencies = {
    "e": Decimal("12.03"),
    "t": Decimal("9.10"),
    "a": Decimal("8.12"),
    "o": Decimal("7.68"),
    "i": Decimal("7.31"),
    "n": Decimal("6.95"),
    "s": Decimal("6.28"),
    "r": Decimal("6.02"),
    "h": Decimal("5.92"),
    "d": Decimal("4.32"),
    "l": Decimal("3.98"),
    "u": Decimal("2.88"),
    "c": Decimal("2.71"),
    "m": Decimal("2.61"),
    "f": Decimal("2.30"),
    "y": Decimal("2.11"),
    "w": Decimal("2.09"),
    "g": Decimal("2.03"),
    "p": Decimal("1.82"),
    "b": Decimal("1.49"),
    "v": Decimal("1.11"),
    "k": Decimal("0.69"),
    "x": Decimal("0.17"),
    "q": Decimal("0.11"),
    "j": Decimal("0.10"),
    "z": Decimal("0.07"),
}
