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
        content="Passwords chosen by humans are easy to guess and lack high-entropy randomness. Symmetric algorithms like AES require uniform 256-bit binary keys. Argon2id derives a cryptographic key from your password and a unique salt. Its memory-hard computation makes large-scale password guessing significantly more expensive.",
        simple_explanation="AES does not understand text passwords. Argon2id derives a 256-bit random cryptographic key from your password and a salt.",
        technical_explanation="Argon2id combines salt + password, performing a configurable number of memory loops (100MB cost, 3 iterations, 8 threads) to resist ASIC/GPU parallelized password-cracking.",
        security_explanation="A sufficiently strong password combined with an appropriate KDF like Argon2id makes practical offline password guessing extremely expensive for attackers."
    ),
    Lesson(
        id="salt_nonce_lab",
        title="Level 3: Salt & Nonce Laboratory",
        category="Salts & Nonces",
        difficulty="Intermediate",
        content="A salt is a unique, random 16-byte value used during key derivation. It ensures identical passwords produce completely different derived keys. Cryptix generates a fresh nonce/IV for each encryption operation. The required size depends on the selected AEAD algorithm (12 bytes for GCM/ChaCha20, 24 bytes for XChaCha20). Nonce reuse with the same key is a critical security vulnerability.",
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
        security_explanation="The password and derived encryption key are not stored in the Cryptix container. Only public, random, and authenticated cryptographic helper headers are stored."
    ),
        Lesson(
        id="integrity_tampering",
        title="Level 7: Integrity & Tampering",
        category="Attack Vector Diagnostics",
        difficulty="Advanced",
        content="An attacker with access to your container can attempt active manipulations. Cryptix defends itself through two distinct layers: Layer 1 (Structural Format Validation) evaluates magic bytes and version compatibilities immediately during parsing. Layer 2 (Cryptographic AEAD Verification) progressively evaluates ciphertext and AAD bytes against the authentication tag, halting decryption cleanly on mismatch.",
        simple_explanation="Cryptix has a two-layer defense. First, it checks if the file structure is correct (Layer 1). Second, it cryptographically verifies that nobody changed the password, name, or content (Layer 2).",
        technical_explanation="Layer 1 parses static header boundaries prior to key processing. Layer 2 executes the AEAD verify sequence, enforcing a strict fail-closed boundary on authentication mismatch.",
        security_explanation="Failing closed prevents adversaries from using modified files to perform active chosen-ciphertext side-channel attacks or memory leakage diagnostics."
    )
]

QUESTIONS = [
    # ---- Level 1: Fundamentals ----
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
        difficulty="Beginner",
        feedback_by_answer={
            "A": "Incorrect. While zip compressing saves space, symmetric cryptography's primary goal is secrecy.",
            "C": "Incorrect. Digital signatures and public-key cryptosystems verify sender identity, not standard symmetric blocks.",
            "D": "Incorrect. Anti-malware software blocks malicious payloads. Cryptography only protects data secrecy."
        }
    ),
    Question(
        id="fundamentals_q2",
        lesson_id="crypto_fundamentals",
        question_type="ordering",
        question="Arrange the conceptual symmetric encryption pipeline in the correct sequential order.",
        options=[
            "Plaintext",
            "Encryption",
            "Ciphertext",
            "Decryption",
            "Plaintext"
        ],
        correct_answer="0,1,2,3,4",
        explanation="Plaintext is encrypted into Ciphertext, which is later decrypted back into Plaintext.",
        difficulty="Beginner"
    ),

    # ---- Level 2: Passwords & Argon2id ----
    Question(
        id="kdf_q1",
        lesson_id="kdf_argon2id",
        question_type="choice",
        question="Why can't Cryptix Core simply use your plaintext password directly as an AES key?",
        options=[
            "A. Text passwords are too short and lack the uniform high-entropy randomness required by AES",
            "B. Plaintext passwords would corrupt the file structure on write",
            "C. Plaintext passwords can only encrypt text files",
            "D. Plaintext passwords would bypass verification checks"
        ],
        correct_answer="A",
        explanation="AES requires a uniform 256-bit high-entropy binary key. Humans choose low-entropy passwords. Argon2id is required to derive a random 256-bit key from the password safely.",
        difficulty="Intermediate",
        feedback_by_answer={
            "B": "Incorrect. Passwords do not corrupt writing systems directly; they are simply mathematically insecure.",
            "C": "Incorrect. Standard passwords can derive keys for any binary file types, but lack the block entropy size required by AES.",
            "D": "Incorrect. A password directly used would bypass nothing, but is easily cracked due to its extremely low entropy."
        }
    ),
    Question(
        id="kdf_q2",
        lesson_id="kdf_argon2id",
        question_type="choice",
        question="If two users choose the exact same password, why should their derived keys still differ?",
        options=[
            "A. The encryption algorithm changes automatically",
            "B. Cryptix forces different version codes",
            "C. A unique random salt is generated for each user, producing unique keys",
            "D. The user email is mixed into the key"
        ],
        correct_answer="C",
        explanation="A unique random salt is combined with the password. This ensures identical passwords derive highly divergent keys, preventing cross-file correlation and dictionary attacks.",
        difficulty="Intermediate",
        feedback_by_answer={
            "A": "Incorrect. The selected algorithm is fully static and does not dynamically alter to generate keys.",
            "B": "Incorrect. Version numbers are global and static. They do not vary based on user passwords.",
            "D": "Incorrect. Cryptix Core is offline and does not collect, mix, or require email IDs."
        }
    ),

    # ---- Level 3: Salts & Nonces ----
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
        difficulty="Intermediate",
        feedback_by_answer={
            "A": "Incorrect. Plaintext file sizes are inherently visible in the ciphertext block length. Nonces do not hide lengths.",
            "C": "Incorrect. Nonces are completely public headers and must NEVER hold copies of sensitive user passwords.",
            "D": "Incorrect. Nonces belong only to the AEAD cipher stream. They have no influence on Argon2 KDF execution speed."
        }
    ),
    Question(
        id="salt_nonce_q2",
        lesson_id="salt_nonce_lab",
        question_type="boolean",
        question="A cryptographic nonce/IV is intended to be safely reused with the same encryption key.",
        options=[
            "True",
            "False"
        ],
        correct_answer="False",
        explanation="A nonce stands for 'number used once'. Reusing a nonce with the same key breaks the semantic security of AEAD ciphers, allowing attackers to leak data.",
        difficulty="Intermediate"
    ),

    # ---- Level 4: AEAD ----
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
        difficulty="Advanced",
        feedback_by_answer={
            "A": "Incorrect. Integrity verification does not influence filesystem size limits.",
            "C": "Incorrect. Failed decryptions do not affect your local persistent settings.json file.",
            "D": "Incorrect. The encryption protocol remains unchanged on file errors."
        }
    ),
    Question(
        id="aead_q2",
        lesson_id="aead_authentication",
        question_type="boolean",
        question="AEAD authenticated encryption guarantees both the confidentiality and integrity of your files.",
        options=[
            "True",
            "False"
        ],
        correct_answer="True",
        explanation="AEAD (Authenticated Encryption with Associated Data) guarantees confidentiality (via encryption) and integrity/authenticity (via tag verification) concurrently.",
        difficulty="Advanced"
    ),

    # ---- Level 5: AAD ----
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
        difficulty="Advanced",
        feedback_by_answer={
            "A": "Incorrect. AAD does not encrypt headers. The filename is readable, but completely authenticated against alteration.",
            "C": "Incorrect. AAD binds the literal raw filename bytes and performs zero compression operations.",
            "D": "Incorrect. Cryptix Core is local-first. It does not send files or names to online APIs."
        }
    ),
    Question(
        id="aad_q2",
        lesson_id="aad_metadata",
        question_type="choice",
        question="What is the main characteristic of Associated Data (AAD)?",
        options=[
            "A. It is encrypted but not verified",
            "B. It remains unencrypted (public) but is completely authenticated against modification",
            "C. It is generated by Argon2id",
            "D. It has a constant length of 256 bytes"
        ],
        correct_answer="B",
        explanation="AAD allows non-secret parameters (like headers and filenames) to remain readable, while fully guaranteeing that they cannot be modified or replaced by an attacker.",
        difficulty="Advanced",
        feedback_by_answer={
            "A": "Incorrect. AAD is exactly the opposite: public but validated. Traditional payload blocks are encrypted and verified.",
            "C": "Incorrect. AAD is composed of plain bytes and is independent of KDF key forge generators.",
            "D": "Incorrect. The filename size is variable, so AAD size expands dynamically to match."
        }
    ),

    # ---- Level 6: Container ----
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
        explanation="Neither your password nor your derived secret key is ever written to the disk. Only random salts, nonces, and tags are saved. Keys are re-derived at runtime.",
        difficulty="Advanced",
        feedback_by_answer={
            "A": "Incorrect. Storing secret parameters inside or near ciphertext blocks allows attackers to decrypt containers directly.",
            "B": "Incorrect. Salt headers are entirely public and cannot hold copy structures of secret derived keys.",
            "D": "Incorrect. Magic headers are constant ASCII labels ('GCA1') and never contain cryptographic passwords."
        }
    ),
    Question(
        id="container_q2",
        lesson_id="container_architecture",
        question_type="ordering",
        question="Arrange the first 5 sequential components of the .cryptix binary header layout.",
        options=[
            "Magic Header (GCA1)",
            "Format Version",
            "Algorithm ID",
            "Key Salt",
            "Nonce/IV"
        ],
        correct_answer="0,1,2,3,4",
        explanation="The container layout reads: Magic Header (4 bytes), version (1 byte), algorithm (1 byte), salt (16 bytes), and nonce/IV (12 or 24 bytes) in exact sequence.",
        difficulty="Advanced"
    ),

    # ---- Level 7: Integrity & Tampering ----
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
        difficulty="Advanced",
        feedback_by_answer={
            "A": "Incorrect. If magic bytes fail to match, the system prevents execution entirely, avoiding decryption attempts.",
            "C": "Incorrect. The tag authenticates data but cannot reconstruct corrupted constants.",
            "D": "Incorrect. Format rejections block the thread and do not trigger settings swaps."
        }
    ),
    Question(
        id="integrity_q2",
        lesson_id="integrity_tampering",
        question_type="choice",
        question="What is Cryptix's response to an authentication tag mismatch during decryption?",
        options=[
            "A. It writes partially corrupted bytes to the filesystem",
            "B. It prompts the user to enter a new salt",
            "C. It halts immediately, throws AuthenticationError, and releases zero plaintext bytes",
            "D. It attempts decryption using a fallback algorithm"
        ],
        correct_answer="C",
        explanation="AEAD guarantees fail-closed security. Any modification or wrong password fails the MAC check. Decryption aborts instantly, releasing zero plaintext bytes to the system.",
        difficulty="Advanced",
        feedback_by_answer={
            "A": "Incorrect. To maintain safety boundaries, zero plaintext bytes are written or released on tag mismatch.",
            "B": "Incorrect. Mismatched MAC checks mean incorrect keys or files. Asking for new salts is mathematically useless.",
            "D": "Incorrect. AEAD boundaries abort execution on failure and do not swap ciphers."
        }
    )
]

def get_lessons():
    return LESSONS

def get_questions_for_lesson(lesson_id: str):
    return [q for q in QUESTIONS if q.lesson_id == lesson_id]

def validate_curriculum() -> None:
    """
    Validation Layer: Ensures curriculum mapping, lesson IDs,
    question formats, options, and answers match all architectural constraints.
    Raises ValueError on any parsing anomaly.
    """
    lesson_ids = {l.id for l in LESSONS}
    
    for l in LESSONS:
        if not l.id or not l.title or not l.simple_explanation or not l.technical_explanation or not l.security_explanation:
            raise ValueError(f"Lesson '{l.id}' is missing required educational explanation fields.")

    for q in QUESTIONS:
        if q.lesson_id not in lesson_ids:
            raise ValueError(f"Question '{q.id}' references an invalid lesson ID: '{q.lesson_id}'.")
        
        if q.question_type not in ["choice", "boolean", "ordering"]:
            raise ValueError(f"Question '{q.id}' has an invalid type: '{q.question_type}'.")

        if not q.correct_answer:
            raise ValueError(f"Question '{q.id}' is missing its correct answer.")

        if q.question_type == "boolean":
            if q.options != ["True", "False"]:
                raise ValueError(f"Boolean Question '{q.id}' options must be exactly ['True', 'False'].")
            if q.correct_answer not in ["True", "False"]:
                raise ValueError(f"Boolean Question '{q.id}' correct answer must be 'True' or 'False'.")
        
        elif q.question_type == "ordering":
            if len(q.options) != 5:
                raise ValueError(f"Ordering Question '{q.id}' must contain exactly 5 elements.")
            if q.correct_answer != "0,1,2,3,4":
                raise ValueError(f"Ordering Question '{q.id}' correct answer must match sequential indexes: '0,1,2,3,4'.")
        
        else:
            # Choice
            if len(q.options) != 4:
                raise ValueError(f"Choice Question '{q.id}' must contain exactly 4 options.")
            if q.correct_answer not in ["A", "B", "C", "D"]:
                raise ValueError(f"Choice Question '{q.id}' correct answer must match standard uppercase option keys (A-D).")
            
            # Every incorrect choice must have custom explanation feedback inside feedback_by_answer dictionary!
            incorrect_keys = [chr(65 + i) for i in range(4) if chr(65 + i) != q.correct_answer]
            for key in incorrect_keys:
                if key not in q.feedback_by_answer:
                    raise ValueError(f"Choice Question '{q.id}' is missing custom explanation feedback for option '{key}'.")
