print("\n-------> LET'S PROCESS SOME TEXT...\n")


print("\nRetrieving dependencies...\n")
import nltk
nltk.download('punkt')
nltk.download('wordnet')
nltk.download('stopwords')
from nltk.stem import WordNetLemmatizer
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords


sentence = "But a kid put his feet in a whole bunch of bats"


#Lowcase
print("\n\nLowcase...\n")
sentence = sentence.lower()
print(sentence)


#Tokenization (split into words)
print("\n\nTokenizing...\n")
tokenized_words = nltk.word_tokenize(sentence)
print(tokenized_words)


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







print("\n\n")