class InvertedIndex:
	def __init__(self):
		self.index = {}

	def add_document(self, document_id, document):
		terms = document.split()
		for position, term in enumerate(terms):
			if term not in self.index:
				self.index[term] = {}
			if document_id not in self.index[term]:
				self.index[term][document_id] = []

			self.index[term][document_id].append(position)

	def search(self, query):
		print(f"\nSearching for: {query}...")
		terms = query.split()
		results = None
		# Search that terms exists in index
		for term in terms:
			if term in self.index:
				# Save document IDs of terms in the index
				if results is None:
					results = set(self.index[term].keys())
				else:
					results.intersection_update(self.index[term].keys())
		if results is None:
			return []
		else:
			search_results = {}
			# For every document ID in results
			for document_id in results:
				positions = []
				for term in terms:
					# Retrieve document positions by document_id, from index
					positions += self.index[term][document_id]
				# And write them in the search results as key/value Document_ID/positions
				if document_id in search_results:
					search_results[document_id].append(positions)
				else:
					search_results[document_id] = positions
			
			if search_results == {}:
				print("Nothing found :(")
			else:
				print(search_results)
			return search_results


			#for document_id, positions in search_results:
			#	print(f"Document id: {document_id}")
			#	print(f"Position(s): {positions}")



# Add stuff
temp_index = InvertedIndex()
temp_index.add_document(1, 'apple banana apple orange orange apple apple lemon')
temp_index.add_document(2, 'apple lemon cherry orange orange orange')
temp_index.add_document(3, 'banana banana banana banana cherry lemon')
print("\nDocs added to the inverted index.")
print(temp_index.index)

# Search stuff
query = 'banana'
search_results = temp_index.search(query)
search_results = temp_index.search('apple')
search_results = temp_index.search('lemon')
#print(f"\nSearching for: {query}...")
#if search_results == {}:
#	print("Nothing found :(")
#else:
#	print(search_results)
	#for document_id, positions in search_results:
	#	print(f"Document id: {document_id}")
	#	print(f"Position(s): {positions}")
