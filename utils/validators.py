import re
from typing import Tuple, Optional

def normalize_phone(phone: str) -> str:
    """
    Telefon raqamini +998XXXXXXXXX formatiga keltirish
    """
    if not phone:
        return ""
    
    # Bo'sh joylar va maxsus belgilarni olib tashlash
    phone = re.sub(r'[^\d+]', '', phone.strip())
    
    # + belgisi bilan boshlangan bo'lsa, uni olib tashlash
    if phone.startswith("+"):
        phone = phone[1:]
    
    # 998 bilan boshlanmagan bo'lsa, qo'shish
    if not phone.startswith("998"):
        # Agar 9 raqam bilan boshlangan bo'lsa (masalan, 901234567)
        if phone.startswith("9") and len(phone) == 9:
            phone = "998" + phone
        # Agar boshqa formatda bo'lsa, 998 qo'shish
        elif not phone.startswith("998"):
            phone = "998" + phone
    
    return f"+{phone}"

def validate_phone(phone: str) -> Tuple[bool, Optional[str]]:
    """
    Telefon raqamini validatsiya qilish
    Returns: (is_valid, error_message)
    """
    if not phone:
        return False, "Telefon raqami kiritilmagan."
    
    # Normalize qilish
    normalized = normalize_phone(phone)
    
    # +998 va undan keyin 9 raqam bo'lishi kerak (jami 13 belgi: +998XXXXXXXXX)
    pattern = r'^\+998\d{9}$'
    
    if re.match(pattern, normalized):
        # Qo'shimcha tekshirish: ikkinchi raqam 9, 8, 7, 6, 5, 3, 4, 0, 1 bo'lishi kerak
        # O'zbekiston operatorlari uchun
        second_digit = normalized[4]  # +998X <- bu X
        valid_operators = ['9', '8', '7', '6', '5', '3', '4', '0', '1', '2']
        
        if second_digit in valid_operators:
            return True, None
        else:
            return False, (
                "Noto'g'ri operator kodi. "
                "O'zbekiston telefon raqami +998 dan keyin 9, 8, 7, 6, 5, 3, 4, 0 yoki 1 bilan boshlanishi kerak.\n"
                "Masalan: +998901234567"
            )
    
    # Xato holatlari uchun batafsil xabarlar
    if len(normalized) < 13:
        return False, (
            "Telefon raqami juda qisqa. "
            "O'zbekiston raqami +998 bilan boshlanib, undan keyin 9 ta raqam bo'lishi kerak.\n"
            "Masalan: +998901234567"
        )
    elif len(normalized) > 13:
        return False, (
            "Telefon raqami juda uzun. "
            "O'zbekiston raqami +998 bilan boshlanib, undan keyin 9 ta raqam bo'lishi kerak.\n"
            "Masalan: +998901234567"
        )
    elif not normalized.startswith("+998"):
        return False, (
            "Telefon raqami +998 bilan boshlanishi kerak.\n"
            "Masalan: +998901234567"
        )
    else:
        return False, (
            "Noto'g'ri telefon raqam formati. "
            "O'zbekiston raqami +998 bilan boshlanib, undan keyin 9 ta raqam bo'lishi kerak.\n"
            "Masalan: +998901234567"
        )

def is_uzbek_phone(phone: str) -> bool:
    """
    Telefon raqami O'zbekiston raqami ekanligini tekshirish
    """
    is_valid, _ = validate_phone(phone)
    return is_valid

