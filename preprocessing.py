import re

# Stop words list (Lecture 2, Slide 60)
STOP_WORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and", 
    "any", "are", "as", "at", "be", "because", "been", "before", "being", "below", 
    "between", "both", "but", "by", "could", "did", "do", "does", "doing", "down", 
    "during", "each", "few", "for", "from", "further", "had", "has", "have", 
    "having", "he", "her", "here", "hers", "herself", "him", "himself", "his", 
    "how", "i", "if", "in", "into", "is", "it", "its", "itself", "me", "more", 
    "most", "my", "myself", "no", "nor", "not", "of", "off", "on", "once", "only", 
    "or", "other", "ought", "our", "ours", "ourselves", "out", "over", "own", 
    "same", "she", "should", "so", "some", "such", "than", "that", "the", "their", 
    "theirs", "them", "themselves", "then", "there", "these", "they", "this", 
    "those", "through", "to", "too", "under", "until", "up", "very", "was", "we", 
    "were", "what", "when", "where", "which", "while", "who", "whom", "why", "with", 
    "would", "you", "your", "yours", "yourself", "yourselves"
}

def tokenize(text, remove_stops=False):
    """Case-folding and token extraction (Lecture 2, Slide 59)."""
    tokens = re.findall(r'\b[a-z0-9]+\b', text.lower())
    if remove_stops:
        return [w for w in tokens if w not in STOP_WORDS]
    return tokens

def compute_soundex(token):
    """Soundex phonetic encoding algorithm (Lecture 3, Slides 130-131)."""
    token = token.upper()
    if not token or not token[0].isalpha():
        return ""
    
    first_letter = token[0]
    mapping = {
        'B': '1', 'F': '1', 'P': '1', 'V': '1',
        'C': '2', 'G': '2', 'J': '2', 'K': '2', 'Q': '2', 'S': '2', 'X': '2', 'Z': '2',
        'D': '3', 'T': '3',
        'L': '4',
        'M': '5', 'N': '5',
        'R': '6'
    }
    
    encoded = []
    prev_code = mapping.get(first_letter, '0')
    
    for ch in token[1:]:
        code = mapping.get(ch, '0')
        if code != '0':
            if code != prev_code:
                encoded.append(code)
            prev_code = code
        else:
            prev_code = '0'
            
    code_str = first_letter + "".join(encoded)
    return (code_str + "000")[:4]

def edit_distance(s1, s2):
    """Dynamic programming Levenshtein distance (Lecture 3, Slide 109)."""
    m, n = len(s1), len(s2)
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(m + 1):
        dp[i][0] = i
    for j in range(n + 1):
        dp[0][j] = j

    for i in range(1, m + 1):
        for j in range(1, n + 1):
            cost = 0 if s1[i - 1] == s2[j - 1] else 1
            dp[i][j] = min(
                dp[i - 1][j] + 1,       # Deletion
                dp[i][j - 1] + 1,       # Insertion
                dp[i - 1][j - 1] + cost # Substitution
            )
    return dp[m][n]

def jaccard_similarity(set1, set2):
    """Jaccard coefficient overlap calculation (Lecture 3, Slide 116)."""
    if not set1 and not set2:
        return 1.0
    intersection = len(set1.intersection(set2))
    union = len(set1.union(set2))
    return intersection / union if union > 0 else 0.0