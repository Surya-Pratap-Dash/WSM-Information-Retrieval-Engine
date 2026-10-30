import os
import math
from collections import Counter, defaultdict
from preprocessing import tokenize, compute_soundex, STOP_WORDS

class DocumentIndex:
    def __init__(self):
        self.doc_names = []
        self.doc_to_id = {}
        self.id_to_doc = {}
        self.raw_docs = {}
        self.doc_lengths = {}
        self.total_docs = 0

        # Positional Inverted Index: term -> {doc_id: [positions]} (Lecture 2, Slide 81)
        self.positional_index = defaultdict(lambda: defaultdict(list))
        # Zone/Parametric Index: zone -> term -> set(doc_ids) (Lecture 6, Slide 232)
        self.zone_index = {
            "title": defaultdict(set),
            "body": defaultdict(set)
        }
        # Permuterm Index: rotated_form -> term (Lecture 3, Slide 95)
        self.permuterm_index = {}
        # Soundex Index: code -> set of terms (Lecture 3, Slide 129)
        self.soundex_index = defaultdict(set)

        self.vocabulary = set()
        self.tf = defaultdict(lambda: Counter())
        self.idf = {}
        self.doc_vectors = {}
        self.doc_magnitudes = {}

    def build_from_folder(self, folder_path):
        self.__init__()
        if not os.path.exists(folder_path):
            return 0

        files = sorted([f for f in os.listdir(folder_path) if f.endswith('.txt')])
        if not files:
            return 0

        for doc_id, fname in enumerate(files):
            full_path = os.path.join(folder_path, fname)
            with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()

            self.doc_names.append(fname)
            self.doc_to_id[fname] = doc_id
            self.id_to_doc[doc_id] = fname
            self.raw_docs[fname] = content

            lines = content.split('\n')
            title_text = lines[0] if lines else ""
            body_text = "\n".join(lines[1:]) if len(lines) > 1 else content

            # Indexing zones (Lecture 6, Slide 232)
            for t in tokenize(title_text, remove_stops=True):
                self.zone_index["title"][t].add(doc_id)
            for t in tokenize(body_text, remove_stops=True):
                self.zone_index["body"][t].add(doc_id)

            # Positional token indexing (Lecture 2, Slide 81)
            tokens = tokenize(content, remove_stops=False)
            self.doc_lengths[fname] = len(tokens)

            for pos, term in enumerate(tokens):
                self.positional_index[term][doc_id].append(pos)
                self.vocabulary.add(term)
                if term not in STOP_WORDS:
                    self.tf[fname][term] += 1

        self.total_docs = len(self.doc_names)
        self._build_auxiliary_indices()
        self._compute_vsm_weights()
        return self.total_docs

    def _build_auxiliary_indices(self):
        for term in self.vocabulary:
            # Soundex (Lecture 3, Slide 129)
            snd = compute_soundex(term)
            if snd:
                self.soundex_index[snd].add(term)

            # Permuterm index for wildcards (Lecture 3, Slide 95)
            aug = term + "$"
            for i in range(len(aug)):
                rot = aug[i:] + aug[:i]
                self.permuterm_index[rot] = term

    def _compute_vsm_weights(self):
        # Inverse Document Frequency: idf = log((N + 1) / (df + 1)) + 1 (Lecture 6, Slide 263)
        for term in self.vocabulary:
            if term in STOP_WORDS:
                continue
            df = len(self.positional_index[term])
            self.idf[term] = math.log((self.total_docs + 1) / (df + 1)) + 1.0

        # Sublinear TF-IDF vector & L2 Normalization (Lecture 7, Slides 276-277)
        for doc in self.doc_names:
            vec = {}
            sum_sq = 0.0
            for term, count in self.tf[doc].items():
                wf = 1.0 + math.log(count) if count > 0 else 0.0
                weight = wf * self.idf[term]
                vec[term] = weight
                sum_sq += weight ** 2

            self.doc_vectors[doc] = vec
            self.doc_magnitudes[doc] = math.sqrt(sum_sq)

    # --- Compression Algorithms (Lecture 5, Slides 186-187, 199) ---
    @staticmethod
    def vb_encode_number(n):
        """Variable Byte encoding for a single integer (Lecture 5, Slide 199)."""
        bytes_list = []
        while True:
            bytes_list.insert(0, n % 128)
            if n < 128:
                break
            n //= 128
        bytes_list[-1] += 128
        return bytes_list

    @staticmethod
    def vb_encode(numbers):
        """Variable Byte encoding for postings gap list (Lecture 5, Slide 199)."""
        bytestream = []
        for n in numbers:
            bytestream.extend(DocumentIndex.vb_encode_number(n))
        return bytes(bytestream)

    @staticmethod
    def vb_decode(bytestream):
        """Variable Byte decoding back to integer sequence (Lecture 5, Slide 199)."""
        numbers = []
        n = 0
        for byte in bytestream:
            if byte < 128:
                n = 128 * n + byte
            else:
                n = 128 * n + (byte - 128)
                numbers.append(n)
                n = 0
        return numbers

    @staticmethod
    def gamma_encode_number(n):
        """Elias Gamma code for gap n (Lecture 5, Slides 186-187)."""
        if n <= 0:
            return ""
        binary = bin(n)[2:]
        offset = binary[1:]
        length = len(offset)
        unary = "1" * length + "0"
        return unary + offset