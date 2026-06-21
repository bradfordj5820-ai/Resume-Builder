import re
from collections import Counter
import nltk
from nltk.corpus import stopwords

# Ensure you have stopwords downloaded
nltk.download('stopwords', quiet=True)
stop_words = set(stopwords.words('english'))

def extract_top_keywords(jd_text, top_n=20):
    """
    Cleans the JD text and extracts the most frequent professional terms.
    """
    # 1. Clean the text: remove special characters, lowercase
    text = re.sub(r'[^\w\s]', '', jd_text.lower())
    words = text.split()
    
    # 2. Filter out stopwords and very short words
    filtered_words = [w for w in words if w not in stop_words and len(w) > 3]
    
    # 3. Count frequencies
    counts = Counter(filtered_words)
    
    # 4. Return top N as a categorized list
    return [word for word, count in counts.most_common(top_n)]
