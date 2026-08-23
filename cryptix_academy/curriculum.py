# cryptix_academy/curriculum.py

from cryptix_academy.models import Lesson, Question

LESSONS = [
    Lesson(
        id="crypto_fundamentals",
        title="Level 1: Cryptography Fundamentals",
        category="Fundamentals",
        difficulty="Beginner",
        content="Cryptography is the science of securing information. It transforms readable data (Plaintext) into unreadable scrambled data (Ciphertext) using a mathematical recipe (Algorithm) and a secret (Key). Symmetric encryption means the same key is used to lock and unlock the data.",
        simple_explanation="Plaintext is what you can read; Ciphertext is the scrambled output; the Key is the secret lock/unlock combination.",
        technical_explanation="Symmetric primitives rely on shared secret keys of uniform high-entropy (e.g. 256 bits). Decryption applies the inverse of the encryption transform block-by-block.",
        security_explanation="Symmetric encryption guarantees confidentiality. Without the key, ciphertext appears completely indistinguishable from random bytes to any offline adversary."
    ),
    Lesson(
        id="kdf_argon2id",
        title="Level 2: Passwords, Keys & Argon2id",
        category="Key Derivation",
        difficulty="Intermediate",
        content="Passwords chosen by humans are easy to guess and have low randomness (entropy). Primitives like AES require highly random 256-bit binary keys. A Key Derivation Function (KDF) like Argon2id converts your low-entropy password into a high-entropy key by performing thousands of memory-hard hash operations.",
        simple_explanation="AES does not understand text passwords. Argon2id converts your password into a 256-bit random cryptographic key.",
        technical_explanation="Argon2id combines salt + password, performing a configurable number of memory loops (100MB cost, 3 iterations) to resist ASIC/GPU parallelized password-cracking.",
        security_explanation="It mitigates high-speed offline dictionary brute-forcing by making password guesses computationally and economically expensive for attackers."
    )
]

QUESTIONS = [
    Question(
        id="fundamentals_q1",
        lesson_id="crypto_fundamentals",
        question_type="choice",
        question="What does standard symmetric encryption primarily guarantee?",
        options=[
            "A. Data compression",
            "B. Confidentiality (unreadable to unauthorized parties)",
            "C. Verification of original sender identity",
            "D. Protection against malware execution"
        ],
        correct_answer="B",
        explanation="Symmetric encryption scrambles plaintext into ciphertext, guaranteeing data confidentiality so that unauthorized parties without the key see only random noise.",
        difficulty="Beginner"
    ),
    Question(
        id="kdf_q1",
        lesson_id="kdf_argon2id",
        question_type="choice",
        question="Why can't Cryptix Core simply use your plaintext password directly as an AES key?",
        options=[
            "A. Text passwords are too short and lack the necessary high-entropy randomness required by AES",
            "B. Plaintext passwords would corrupt the file structure on write",
            "C. Plaintext passwords can only encrypt text files",
            "D. Plaintext passwords would bypass verification checks"
        ],
        correct_answer="A",
        explanation="AES requires a uniform 256-bit high-entropy binary key. Humans choose low-entropy passwords. Argon2id is required to derive a random 256-bit key from the password safely.",
        difficulty="Intermediate"
    )
]

def get_lessons():
    return LESSONS

def get_questions_for_lesson(lesson_id: str):
    return [q for q in QUESTIONS if q.lesson_id == lesson_id]