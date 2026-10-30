import math
import re
from collections import Counter, defaultdict
from preprocessing import tokenize, STOP_WORDS

class SearchEngineCore:
    def __init__(self, index):
        self.idx = index

    def resolve_wildcard(self, wildcard_query):
        """Permuterm wildcard query evaluation (Lecture 3, Slides 95-96)."""
        wildcard_query = wildcard_query.lower()
        if '*' not in wildcard_query:
            return [wildcard_query] if wildcard_query in self.idx.vocabulary else []

        parts = wildcard_query.split('*')
        if len(parts) == 2:
            lead, trail = parts
            lookup_key = f"{trail}${lead}"
        else:
            regex_pat = "^" + wildcard_query.replace("*", ".*") + "$"
            return [t for t in self.idx.vocabulary if re.match(regex_pat, t)]

        matches = set()
        for rot, orig in self.idx.permuterm_index.items():
            if rot.startswith(lookup_key):
                matches.add(orig)
        return list(matches)

    def search_boolean(self, query):
        """Linear Merge Boolean Search: AND, OR, NOT (Lecture 1, Slides 20-22)."""
        tokens = query.strip().split()
        if not tokens:
            return []

        all_doc_ids = set(range(self.idx.total_docs))
        result = None
        current_op = "AND"
        i = 0

        while i < len(tokens):
            tok = tokens[i]
            upper_tok = tok.upper()

            if upper_tok in ("AND", "OR", "NOT"):
                current_op = upper_tok
                i += 1
                continue

            if '*' in tok:
                matching_terms = self.resolve_wildcard(tok)
                matching_docs = set()
                for t in matching_terms:
                    matching_docs.update(self.idx.positional_index[t].keys())
            else:
                cleaned = tokenize(tok, remove_stops=False)
                if not cleaned:
                    i += 1
                    continue
                matching_docs = set(self.idx.positional_index[cleaned[0]].keys())

            if result is None:
                result = matching_docs
            else:
                if current_op == "AND":
                    result = result.intersection(matching_docs)
                elif current_op == "OR":
                    result = result.union(matching_docs)
                elif current_op == "NOT":
                    result = result.difference(matching_docs)
            i += 1

        res_ids = result if result is not None else set()
        return [(self.idx.id_to_doc[doc_id], 1.0) for doc_id in sorted(res_ids)]

    def search_phrase(self, phrase):
        """Exact phrase retrieval using Positional Index (Lecture 2, Slide 83)."""
        tokens = tokenize(phrase, remove_stops=False)
        if not tokens:
            return []

        common_docs = set.intersection(*(set(self.idx.positional_index[t].keys()) for t in tokens if t in self.idx.positional_index))
        if not common_docs:
            return []

        matched_docs = []
        for doc_id in sorted(common_docs):
            first_positions = self.idx.positional_index[tokens[0]][doc_id]
            for pos in first_positions:
                found = True
                for offset, token in enumerate(tokens[1:], start=1):
                    if (pos + offset) not in self.idx.positional_index[token][doc_id]:
                        found = False
                        break
                if found:
                    matched_docs.append(self.idx.id_to_doc[doc_id])
                    break
        return [(doc, 1.0) for doc in matched_docs]

    def search_proximity(self, term1, term2, k=3):
        """Positional Proximity Search: term1 /k term2 (Lecture 2, Slide 84)."""
        t1, t2 = term1.lower(), term2.lower()
        if t1 not in self.idx.positional_index or t2 not in self.idx.positional_index:
            return []

        postings1 = self.idx.positional_index[t1]
        postings2 = self.idx.positional_index[t2]
        common_docs = set(postings1.keys()).intersection(postings2.keys())
        matched_docs = []

        for doc_id in sorted(common_docs):
            pos1_list = postings1[doc_id]
            pos2_list = postings2[doc_id]
            i, j = 0, 0
            while i < len(pos1_list) and j < len(pos2_list):
                if abs(pos1_list[i] - pos2_list[j]) <= k:
                    matched_docs.append(self.idx.id_to_doc[doc_id])
                    break
                elif pos1_list[i] < pos2_list[j]:
                    i += 1
                else:
                    j += 1

        return [(doc, 1.0) for doc in matched_docs]

    def search_zone(self, term, title_weight=0.6, body_weight=0.4):
        """Linear Zone Scoring: Score = g_title * w_title + g_body * w_body (Lecture 6, Slide 237)."""
        t = term.lower()
        title_docs = self.idx.zone_index["title"].get(t, set())
        body_docs = self.idx.zone_index["body"].get(t, set())
        all_docs = title_docs.union(body_docs)

        scores = {}
        for doc_id in all_docs:
            s = 0.0
            if doc_id in title_docs:
                s += title_weight
            if doc_id in body_docs:
                s += body_weight
            scores[self.idx.id_to_doc[doc_id]] = s

        return sorted(scores.items(), key=lambda x: x[1], reverse=True)

    def search_vsm(self, query_tokens):
        """Cosine Similarity in tf-idf Vector Space (Lecture 7, Slides 276-277)."""
        counts = Counter(query_tokens)
        q_vec = {}
        sum_sq = 0.0

        for term, count in counts.items():
            if term in self.idx.idf:
                wf = 1.0 + math.log(count) if count > 0 else 0.0
                w = wf * self.idx.idf[term]
                q_vec[term] = w
                sum_sq += w ** 2

        q_mag = math.sqrt(sum_sq)
        if q_mag == 0.0:
            return []

        scores = {}
        for doc in self.idx.doc_names:
            d_mag = self.idx.doc_magnitudes[doc]
            if d_mag == 0.0:
                continue

            dot = sum(w * self.idx.doc_vectors[doc].get(t, 0.0) for t, w in q_vec.items())
            sim = dot / (q_mag * d_mag)
            if sim > 0:
                scores[doc] = sim

        return sorted(scores.items(), key=lambda x: x[1], reverse=True)

    def rocchio_feedback(self, original_tokens, rel_docs, non_rel_docs, alpha=1.0, beta=0.75, gamma=0.15):
        """SMART Rocchio Relevance Feedback Formula (Lecture 9, Slide 375)."""
        q_vec = defaultdict(float)
        for term in original_tokens:
            if term in self.idx.idf:
                q_vec[term] += alpha * (1.0 + math.log(1)) * self.idx.idf[term]

        if rel_docs:
            for doc in rel_docs:
                for term, val in self.idx.doc_vectors[doc].items():
                    q_vec[term] += (beta / len(rel_docs)) * val

        if non_rel_docs:
            for doc in non_rel_docs:
                for term, val in self.idx.doc_vectors[doc].items():
                    q_vec[term] -= (gamma / len(non_rel_docs)) * val

        # Ignore negative term weights (Lecture 9, Slide 375)
        refined_vec = {k: v for k, v in q_vec.items() if v > 0}
        q_mag = math.sqrt(sum(v ** 2 for v in refined_vec.values()))
        if q_mag == 0:
            return []

        scores = {}
        for doc in self.idx.doc_names:
            d_mag = self.idx.doc_magnitudes[doc]
            if d_mag == 0.0:
                continue
            dot = sum(w * self.idx.doc_vectors[doc].get(t, 0.0) for t, w in refined_vec.items())
            sim = dot / (q_mag * d_mag)
            if sim > 0:
                scores[doc] = sim

        return sorted(scores.items(), key=lambda x: x[1], reverse=True)

    def pseudo_relevance_feedback(self, query_tokens, top_k_docs=3):
        """Pseudo-Relevance Feedback: Assume top k are relevant (Lecture 9, Slide 407)."""
        initial_results = self.search_vsm(query_tokens)
        if not initial_results:
            return []
        assumed_rel = [doc for doc, _ in initial_results[:top_k_docs]]
        assumed_non_rel = [doc for doc, _ in initial_results[top_k_docs:]]
        return self.rocchio_feedback(query_tokens, assumed_rel, assumed_non_rel)

    def generate_kwic(self, doc_name, query_tokens, window=25):
        """Dynamic Snippet Generation / KWIC (Lecture 8, Slides 323-324)."""
        raw = self.idx.raw_docs.get(doc_name, "")
        tokens = tokenize(raw, remove_stops=False)
        q_set = set(query_tokens)

        positions = [i for i, t in enumerate(tokens) if t in q_set]
        if not positions:
            words = raw.split()
            return " ".join(words[:window]) + "..."

        mid = positions[0]
        start = max(0, mid - window // 2)
        end = min(len(tokens), mid + window // 2)
        return f"... {' '.join(tokens[start:end])} ..."

    @staticmethod
    def evaluate_retrieval(retrieved, relevant):
        """Precision, Recall, and F1 measure (Lecture 8, Slides 334, 339)."""
        ret_set = set(retrieved)
        rel_set = set(relevant)
        tp = len(ret_set.intersection(rel_set))
        fp = len(ret_set - rel_set)
        fn = len(rel_set - ret_set)

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
        return precision, recall, f1