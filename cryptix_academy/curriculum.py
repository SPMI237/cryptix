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
        content="Passwords chosen by humans are easy to guess and lack high-entropy randomness. Symmetric algorithms like AES require uniform 256-bit binary keys. A Key Derivation Function (KDF) like Argon2id derives a cryptographic key from your password and a unique salt. Its memory-hard computation makes large-scale password guessing significantly more expensive.",
        simple_explanation="AES does not understand text passwords. Argon2id converts your password and a salt into a 256-bit random cryptographic key.",
        technical_explanation="Argon2id combines salt + password, performing a configurable number of memory loops (100MB cost, 3 iterations, 8 threads) to resist ASIC/GPU parallelized password-cracking.",
        security_explanation="A sufficiently strong password combined with an appropriate KDF like Argon2id makes practical offline password guessing extremely expensive for attackers."
    ),
    Lesson(
        id="salt_nonce_lab",
        title="Level 3: Salt & Nonce Laboratory",
        category="Salts & Nonces",
        difficulty="Intermediate",
        content="A salt is a unique, random 16-byte value used during key derivation. It ensures identical passwords produce completely different derived keys. A nonce (number used once) or IV is a unique, random 12-byte or 24-byte value that ensures encrypting the same file twice produces completely different ciphertext. Nonce reuse with the same key is a critical security vulnerability.",
        simple_explanation="Salts make passwords unique. Nonces make ciphers unique. They ensure that even if you encrypt the same file twice with the same password, the outputs look completely different.",
        technical_explanation="Salts prevent precomputed dictionary (rainbow table) attacks. Nonces ensure semantic security in authenticated ciphers like AES-GCM (12 bytes) and XChaCha20-Poly1305 (24 bytes).",
        security_explanation="Using a 24-byte nonce (XChaCha20) expands the nonce space from 96 bits to 192 bits, mathematically eliminating random collision risks during automated bulk operations."
    ),
    Lesson(
        id="aead_authentication",
        title="Level 4: AEAD & Authentication",
        category="AEAD & Integrity",
        difficulty="Advanced",
        content="Authenticated Encryption with Associated Data (AEAD) provides both confidentiality (encryption) and authenticity (integrity). It computes a 16-byte digital seal called an Authentication Tag. If even a single bit of the file is modified on disk, the tag verification will fail, and Cryptix will abort decryption without releasing partial plaintext.",
        simple_explanation="Traditional ciphers only hide data. AEAD ciphers hide data AND verify that nobody has modified or corrupted it.",
        technical_explanation="AEAD constructions (like GCM and Poly1305) ingest ciphertext and associated data to compute a MAC tag. Decryption applies a fail-closed verification, raising AuthenticationError on mismatch.",
        security_explanation="It prevents bit-flipping attacks, storage corruption, and wrong-password decryption by refusing to release unauthenticated plaintext before the tag is verified."
    ),
    Lesson(
        id="aad_metadata",
        title="Level 5: AAD & Metadata Binding",
        category="Associated Data",
        difficulty="Advanced",
        content="Associated Data (AAD) is non-secret information (like file headers, version bytes, algorithm IDs, and original filenames) that must remain public but completely unmodifiable. By binding this metadata into the AEAD cipher, Cryptix ensures that any attempt by an attacker to silently alter version bytes, algorithm selectors, or filenames is detected instantly.",
        simple_explanation="Associated Data protects file headers and filenames. An attacker cannot secretly rename your file or change its format parameters without breaking verification.",
        technical_explanation="The cipher.update(aad) stream method processes public header bytes before payload blocks. The resulting tag authenticates both the metadata and the ciphertext concurrently.",
        security_explanation="Metadata authentication prevents silent format tampering, algorithm-swapping exploits, and unauthorized file renaming or replacement attacks."
    ),
    Lesson(
        id="container_architecture",
        title="Level 6: Container Architecture",
        category="File Structure",
        difficulty="Advanced",
        content="The Cryptix Container Format (.cryptix) is a byte-aligned structured binary layout. It sequentially stores: Magic Header (4 bytes 'GCA1'), Format Version (1 byte), Algorithm ID (1 byte), Key Salt (16 bytes), Nonce/IV (12 or 24 bytes), Authentication Tag (16 bytes), Filename Length (4 bytes), Filename (variable), and the encrypted Ciphertext.",
        simple_explanation="A .cryptix file is not a text document. It is a precise, formatted binary container holding magic identifiers, salts, nonces, tags, and ciphertext in sequence.",
        technical_explanation="The container layout uses big-endian 4-byte length prefixing for filenames. Dynamic IV-header offsets ensure compatibility between 12-byte (AES/ChaCha) and 24-byte (XChaCha) nonces.",
        security_explanation="No secret parameters (passwords, encryption keys) are ever written to the disk. Only public, random, and authenticated cryptographic helper headers are stored."
    ),
    Lesson(
        id="integrity_tampering",
        title="Level 7: Integrity & Tampering",
        category="Attack Vector Diagnostics",
        difficulty="Advanced",
        content="An attacker with access to your encrypted container can attempt various active manipulations: flipping bits in ciphertext, altering version codes, or swapping tags. Cryptix operates on a strict fail-closed boundary: any integrity check mismatch causes decryption to halt instantly. Releasing unverified partially decrypted plaintext can leak cryptographic secrets.",
        simple_explanation="If someone tampers with your file, Cryptix doesn't try to repair it. It shuts down decryption instantly to protect you from reading corrupted or leaked data.",
        technical_explanation="Releasing unauthenticated plaintext before tag verification exposes the system to active chosen-ciphertext attacks. A strict fail-closed boundary prevents this.",
        security_explanation="Fail-closed behavior guarantees that an adversary can never gain insight into the plaintext or the key material through progressive, fuzzed alterations."
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
    ),
    Question(
        id="salt_nonce_q1",
        lesson_id="salt_nonce_lab",
        question_type="choice",
        question="Why does Cryptix generate a unique Nonce/IV for every single encryption operation?",
        options=[
            "A. To hide the size of the original file",
            "B. To ensure that encrypting the same file twice produces completely different ciphertext",
            "C. To store a backup of the user password",
            "D. To double the speed of the key derivation function"
        ],
        correct_answer="B",
        explanation="Nonces/IVs ensure semantic security. If the same file is encrypted twice with the same key, different nonces guarantee completely different ciphertexts, preventing pattern leaks.",
        difficulty="Intermediate"
    ),
    Question(
        id="aead_q1",
        lesson_id="aead_authentication",
        question_type="choice",
        question="What is the main danger of decrypting and releasing unverified, tampered plaintext?",
        options=[
            "A. The file size will increase on disk",
            "B. It exposes the system to serious chosen-ciphertext attacks and leaks data structures to attackers",
            "C. It automatically resets the user settings",
            "D. It switches the algorithm back to AES"
        ],
        correct_answer="B",
        explanation="Releasing unauthenticated plaintext is a critical security vulnerability. Attackers can manipulate ciphertext bytes and observe decrypted outputs to reverse-engineer data.",
        difficulty="Advanced"
    ),
    Question(
        id="aad_q1",
        lesson_id="aad_metadata",
        question_type="choice",
        question="How does Additional Authenticated Data (AAD) protect the original filename?",
        options=[
            "A. It encrypts the filename so nobody can see it",
            "B. It binds the filename bytes into the integrity tag, ensuring any name changes break verification",
            "C. It compresses the filename to save header space",
            "D. It uploads the filename to a secure verification server"
        ],
        correct_answer="B",
        explanation="AAD is not encrypted (it remains public in the header), but it is cryptographically bound into the integrity check. Changing a single character in the filename breaks the MAC check.",
        difficulty="Advanced"
    ),
    Question(
        id="container_q1",
        lesson_id="container_architecture",
        question_type="choice",
        question="Where are the user's password and secret encryption keys stored in a .cryptix container?",
        options=[
            "A. At the very end of the ciphertext block",
            "B. Combined directly with the Salt header",
            "C. They are NEVER stored on the disk; only public random parameters are saved",
            "D. Encrypted inside the Magic Header block"
        ],
        correct_answer="C",
        explanation="Cryptix Core operates on zero-knowledge local storage. Neither your password nor yourderived secret key is ever written to the disk. Only random salts, nonces, and tags are saved.",
        difficulty="Advanced"
    ),
    Question(
        id="integrity_q1",
        lesson_id="integrity_tampering",
        question_type="choice",
        question="If an attacker changes the Magic Header 'GCA1' to 'BAD1', what is the security result?",
        options=[
            "A. Decryption succeeds but displays corrupted text",
            "B. The container is rejected immediately on parse as an invalid format, blocking execution",
            "C. Cryptix attempts to repair the magic header using the tag",
            "D. The algorithm selector switches automatically to ChaCha"
        ],
        correct_answer="B",
        explanation="The Magic Header is evaluated in the first step. If the first 4 bytes do not match 'GCA1', the parser raises a FormatError immediately, aborting the workflow before any key processing starts.",
        difficulty="Advanced"
    )
]

def get_lessons():
    return LESSONS

def get_questions_for_lesson(lesson_id: str):
    return [q for q in QUESTIONS if q.lesson_id == lesson_id]
