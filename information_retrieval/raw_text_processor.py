print("\n-------> LET'S PROCESS SOME TEXT...\n")


print("\nRetrieving dependencies...\n")
import nltk
nltk.download('punkt')
nltk.download('wordnet')
nltk.download('stopwords')
from nltk.stem import WordNetLemmatizer
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords
from nltk.stem import PorterStemmer
import math


sentence = "But a kid jumped and twisted and put his feet in a whole bunch of furious bats"

corpus = {
	'doc1' : "the quick brown fox",
	'doc2' : "jumped over the lazy dog",
	'doc3' : "the quick brown fox jumped over the lazy dog",
	'doc4 ' :"the lazy dog slept",
	'doc5' : "the brown fox sleeps",
}


#Lowcase
print("\n\nLowcase...\n")
sentence = sentence.lower()
print(sentence)


#Tokenization (split into words)
print("\n\nTokenizing...\n")
tokenized_words = nltk.word_tokenize(sentence)
print(tokenized_words)

def tokenize(doc):
	tokenized_words = nltk.word_tokenize(doc)
	return tokenized_words


# Removing stop words
print("\n\nStop words...\n")
stop_words = set(stopwords.words('english'))
#print(stop_words)
words = tokenized_words
filtered_words = []
for word in words:
	if word not in stop_words:
		filtered_words.append(word)
#filtered_text = ' '.join(filtered_words)
print(filtered_words)


# Lemmatization (singulars)
print("\n\nLemmatizing...\n")
lemmatizer = WordNetLemmatizer()
lemmatized_words = [lemmatizer.lemmatize(word) for word in filtered_words]
print(lemmatized_words)


# Stemming (Port)
print("\n\nStemming the Port way...\n")
stemmer = PorterStemmer()
stemmed_words = [stemmer.stem(word) for word in lemmatized_words]
for i,t in enumerate(lemmatized_words):
	print(lemmatized_words[i], "->", stemmed_words[i])


#Term Frequency - Inverse Document Frequency
print("\n\nTF-IDF...\n")
def tfidf(term,doc):
	# term in document / document length
	tf = doc.count(term)/len(tokenize(doc))
	# (log:) total documents / total word count in documents
	idf = math.log(len(corpus)/(0.0000000000000001 + sum( 1 for d in corpus.values() if term in tokenize(d)))) # revisar -> a veces divide por cero
				### HAY QUE REVISAR LO DE QUE NO PUEDA DIVIDIR POR CERO
	return tf * idf

def tfidf_vect(doc):
	vector = {}
	# for every term in a document, retrieve the value of its dimension (= Term Frequency * Inverse Document Frequency)
	for term in set(tokenize(doc)):
		vector[term] = tfidf(term,doc)
	return vector


vectors = {}

for doc_id, doc in corpus.items():
	vectors[doc_id] = tfidf_vect(doc)

def cosine_similarity(vec1,vec2):
	dot_product = sum( vec1.get(term,0) * vec2.get(term,0) for term in set(vec1) & set(vec2))
	norm1 = math.sqrt(sum(val**2 for val in vec1.values())) # la raíz cuadrada del sumatorio de todos los valores del vector al cuadrado
	norm2 = math.sqrt(sum(val**2 for val in vec2.values()))
	return dot_product / (norm1 * norm2)

def vector_space_retrieval(query):
	query_vec = tfidf_vect(query)
	results = []
	for doc_id, doc_vec in vectors.items():
		score = cosine_similarity(query_vec, doc_vec)
		results.append((doc_id,score)) # interesante forma de hacerlo
	results.sort(key = lambda x: x[1], reverse=True)
	return results

def search(query):
	results = vector_space_retrieval(query)
	print(f"Results for query: {query}")
	for doc_id, score in results:
		print(f"{doc_id} : {score}")
	print("\n")
	return results

search("brown fox")
search("quick brown dog")
print(search("dog jumped"))

# esta falla: search("over lazy dog fox sleep")

