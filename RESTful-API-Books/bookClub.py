import google.generativeai as genai
import os
from flask import Flask, jsonify, request
from flask_restful import Api, Resource
import requests
import uuid


app = Flask(__name__)
api = Api(app)

books = []
ratings = []
top_books_global = []


class Books(Resource):
    def get(self):
        args = request.args
        filtered_books = []
        if args:
            # Initialize a list to store filters for "and" conditions
            query_fields = {}
            # Handle special query for language
            if 'language' in args:
                lang = args['language']
                for book in books:
                    if lang in book.get('language', []):
                        filtered_books.append(book)
            # Filter based on other field=value queries
            for key, value in args.items():
                if key not in ['summary', 'language']:
                    query_fields[key] = value
            for book in books:
                perfect_match = True
                for query_field, query_value in query_fields.items():
                    if book.get(query_field) != query_value:
                        perfect_match = False
                        break
                if perfect_match:
                    filtered_books.append(book)
        else:
            filtered_books = books
        return filtered_books, 200

    def post(self):
        try:
            # Check if the mediaType is JSON
            if request.headers['Content-Type'] != 'application/json':
                return {'error': 'Unsupported Media Type: Only JSON is supported.'}, 415

            data = request.json

            # Check if there's a missing field
            if not all(field in data for field in ['title', 'ISBN', 'genre']):
                return {'message': 'Unprocessable entity: Missing required fields'}, 422

            if not data['title'].split() or not data['ISBN'].split():
                return {'message': 'Unprocessable entity: Empty fields are not accepted'}, 422

            if not data['ISBN'].isdigit() or len(data['ISBN']) != 13:
                return {'message': 'Unprocessable entity: ISBN must be only 13 numbers'}, 422

            # Check for invalid genre
            accepted_genres = ['Fiction', 'Children', 'Biography', 'Science', 'Science Fiction', 'Fantasy', 'Other']
            if data['genre'] not in accepted_genres:
                return {'message': 'Unprocessable entity: Invalid genre value'}, 422

            # Search for the book by ISBN
            existing_book = next((book for book in books if book['ISBN'] == data['ISBN']), None)

            if existing_book:
                # Book already exists
                return {'message': 'Error: Book already exists'}, 422
            else:
                try:
                    # Fetch additional book information from Google Books API
                    google_books_url = f'https://www.googleapis.com/books/v1/volumes?q=isbn:{data["ISBN"]}'
                    response1 = requests.get(google_books_url)
                    google_books_data = response1.json()['items'][0]['volumeInfo']
                except Exception as e:
                    return {'message': f'Error fetching book data from Google Books API:{str(e)}'}, 500
                    # Fetch additional book information from Google Books API
                authors = ' and '.join(google_books_data.get('authors', ['missing']))
                publisher = google_books_data.get('publisher', 'missing')
                publishedDate = check_date_format(google_books_data.get('publishedDate', 'missing'))

                open_library_data = f'https://openlibrary.org/search.json?q=isbn:{data["ISBN"]}'
                response2 = requests.get(open_library_data)
                try:
                    open_library_data = response2.json()['docs'][0]['language']
                except Exception as e:
                    return {'message': f'Error fetching book data from Open Library:{str(e)}'}, 500
                language = open_library_data

                try:
                    summary = generateAi(data['title'], authors)
                except Exception as e:
                    return {'message': f'Error fetching book data from Gemini:{str(e)}'}, 500
                book_id = str(uuid.uuid4())  # generate a unique id for each book

                book = {
                    'title': data['title'],
                    'authors': authors,
                    'ISBN': data['ISBN'],
                    'genre': data['genre'],
                    'publisher': publisher,
                    'publishedDate': publishedDate,
                    'language': language,
                    'summary': summary,
                    'id': book_id
                }
                books.append(book)
                # Create a rating space for this book
                rating = {
                    'values': [],
                    'average': 0.0,
                    'title': data['title'],
                    'id': book_id
                }
                ratings.append(rating)
                return book_id, 201
        except Exception as e:
            return {'Invalid JSON file': str(e)}, 422


class BooksId(Resource):
    def get(self, id):
        right_book = []
        book = next((book for book in books if book['id'] == id), None)
        if book:
            right_book.append(book)
            return right_book, 200
        else:
            return {'message': 'Not Found: Book not found'}, 404

    def put(self, id):
        try:
            global books
            # Check if the book exists
            book = next((book for book in books if book['id'] == id), None)
            if not book:
                return {'message': 'Not Found: Book not found'}, 404

            # Check if the mediaType is JSON
            if request.headers['Content-Type'] != 'application/json':
                return {'error': 'Unsupported Media Type: Only JSON is supported.'}, 415

            # Get the JSON payload from the request
            data = request.json

            fields = ['title', 'ISBN', 'genre', 'authors', 'publisher', 'publishedDate', 'language', 'summary', 'id']

            # Check if there's a missing field
            if not all(field in data for field in fields):
                return {'message': 'Unprocessable entity: Missing required fields'}, 422

            for field in fields:
                if field != 'language':
                    if not data[f'{field}'].split():
                        return {'message': 'Unprocessable entity: Empty fields are not accepted'}, 422

            if len(data['language']) == 0:
                return {'message': 'Unprocessable entity: Empty fields are not accepted'}, 422

            if not data['ISBN'].isdigit() or len(data['ISBN']) != 13:
                return {'message': 'Unprocessable entity: ISBN must be only 13 numbers'}, 422

            # Check for invalid genre
            accepted_genres = ['Fiction', 'Children', 'Biography', 'Science', 'Science Fiction', 'Fantasy', 'Other']
            if data['genre'] not in accepted_genres:
                return {'message': 'Unprocessable entity: Invalid genre value'}, 422

            # Update the book fields
            for field in data:
                if field == 'publishedDate':
                    book[field] = check_date_format(data['publishedDate'])
                else:
                    book[field] = data[field]

            for rating in ratings:
                if rating['id'] == id:
                    rating['title'] = data['title']
            # Return success message and the ID of the updated resource
            return id, 200
        except Exception as e:
            return {'Invalid JSON file': str(e)}, 422

    def delete(self, id):
        global books
        book_found = False
        for book in books:
            if book['id'] == id:
                books.remove(book)
                book_found = True
                break
        if not book_found:
            return {'message': 'Not Found: Book not found'}, 404
        else:
            for rating in ratings:
                if rating['id'] == id:
                    ratings.remove(rating)
                    break
            return id, 200


class Ratings(Resource):
    def get(self):
        # Get the value of the 'id' query string parameter, if provided
        book_id = request.args.get('id')
        exists = False
        if book_id:
            for rating in ratings:
                if book_id == rating['id']:
                    exists = True
                    break
            if not exists:
                return {'message': 'Not Found: book not found'}, 404

            rating = RatingsId().get(book_id)
            return rating[0], 200
        else:
            # If the 'id' parameter is not provided, return all ratings
            return ratings, 200


class RatingsId(Resource):
    def get(self, id):
        rating = next((rating for rating in ratings if rating['id'] == id), None)
        if rating:
            values = rating.get("values")
            return {'Ratings': values}, 200
        else:
            return {'message': 'Not Found: book not found'}, 404


class RatingsIdValues(Resource):
    def post(self, id):
        try:
            if request.headers['Content-Type'] != 'application/json':
                return {'error': 'Unsupported Media Type: Only JSON is supported.'}, 415

            data = request.json

            exists = False
            for rating in ratings:
                if id == rating['id']:
                    exists = True
                    break
            if not exists:
                return {'message': 'Not Found: book not found'}, 404

            # Check if there's a missing field
            if 'value' not in data:
                return {'message': 'Unprocessable entity: You should enter a value field'}, 422

            value = data.get('value')

            if value not in [1, 2, 3, 4, 5]:
                return {'message': 'Unprocessable entity: A value should be a 1-5 integer'}, 422

            # Add the rating
            rating = next((rating for rating in ratings if rating['id'] == id), None)
            rating['values'].append(value)
            # Recalculate average rating
            avg = round(sum(rating['values']) / len(rating['values']), 2)
            rating['average'] = avg
            return {'Current average': avg}, 201
        except Exception as e:
            return {'Missing value field': str(e)}, 422


class TopBooks(Resource):
    def get(self):
        # Compute the top-rated books dynamically
        top_books = self.compute_top_books()

        if top_books:
            return top_books, 200
        else:
            return [], 200

    def compute_top_books(self):
        global top_books_global
        top_books_global = []
        # Filter out books with less than 3 ratings
        eligible_rating = [rating for rating in ratings if len(rating['values']) >= 3]

        if not eligible_rating:
            return []

        # Sort the eligible books by average rating in descending order
        sorted_books = sorted(eligible_rating, key=lambda x: x['average'], reverse=True)

        # Get the top 3 books by average rating
        top_books = sorted_books[:min(3, len(sorted_books))]

        # Find the threshold average rating (average rating of the third book)
        threshold_average = top_books[-1]['average']
        if(len(sorted_books)) > 3:
            # Check if there are additional books with the same score as the third book
            additional_books = [rating for rating in sorted_books[3:] if rating['average'] == threshold_average]

            # Include additional books if they have the same score as the third book
            top_books.extend(additional_books)

        for book in top_books:
            top_book = {
                'id': book['id'],
                'title': book['title'],
                'average': next((rating for rating in ratings if rating['id'] == book['id']), None).get('average')
            }
            top_books_global.append(top_book)
        return top_books_global


def generateAi(name, authors):
    genai.configure(api_key='API-KEY-HERE')
    model = genai.GenerativeModel('gemini-pro')
    response = model.generate_content(f"Summarize the book '{name}' by {authors} in 5 sentences or less.")
    return response.text


def check_date_format(date_str):
    # Check if the length of the string is either 4 (for 'yyyy') or 10 (for 'yyyy-mm-dd')
    if len(date_str) == 4 or len(date_str) == 10:
        if len(date_str) == 4:
            # Check if all characters in the string are digits
            if date_str.isdigit():
                return date_str
        elif len(date_str) == 10:
            # Check if the first 4 characters are digits and the 5th and 8th characters are '-'
            if date_str[:4].isdigit() and date_str[4] == '-' and date_str[7] == '-':
                return date_str
    return "missing"


api.add_resource(Books, "/books")
api.add_resource(BooksId, "/books/<string:id>")
api.add_resource(Ratings, "/ratings")
api.add_resource(RatingsId, "/ratings/<string:id>")
api.add_resource(RatingsIdValues, "/ratings/<string:id>/values")
api.add_resource(TopBooks, "/top")

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=8000, debug=True)
