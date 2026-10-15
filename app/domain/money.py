def format_rub(kopecks: int) -> str:
    rub, kop = divmod(kopecks, 100)
    return f"{rub:,}".replace(",", " ") + f",{kop:02d} ₽"
