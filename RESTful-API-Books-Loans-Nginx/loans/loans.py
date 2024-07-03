import os
import json
import pymongo as pymongo
from flask import Flask, request
from flask_restful import Api, Resource
import requests
import uuid

app = Flask(__name__)
api = Api(app)

client = pymongo.MongoClient("mongodb://mongo:27017/")
db = client["Library"]
loan_collection = db["LoansDB"]
users_ids = db["UsersIds"]


class loans(Resource):
    def get(self):
        args = request.args
        query = {}
        if args:
            for key, value in args.items():
                query[key] = value
        matching_loans = list(loan_collection.find(query, {'_id': 0}))  # Exclude MongoDB's internal ID from the results
        return matching_loans, 200

    def post(self):
        try:
            # Check if the mediaType is JSON
            if request.headers['Content-Type'] != 'application/json':
                return {'error': 'Unsupported Media Type: Only JSON is supported.'}, 415

            data = request.json

            # Check if there's a missing field
            if not all(field in data for field in ['memberName', 'ISBN', 'loanDate']):
                return {'message': 'Unprocessable entity: Missing required fields'}, 422

            if not data['memberName'].split() or not data['ISBN'].split() or not data['loanDate'].split():
                return {'message': 'Unprocessable entity: Empty fields are not accepted'}, 422

            if loan_collection.find_one({'ISBN': data['ISBN']}):
                return {'message': 'Error: Book already lent'}, 422

            try:
                # Search for the book in book resource by ISBN
                our_books_url = f'http://books:5001/books?ISBN={data["ISBN"]}'

                response = requests.get(our_books_url)
                response_data = response.json()
                # Check if the book exists in the response data
                if not response_data:
                    return {'message': f'Book does not exist in the library'}, 422

                book_title = response_data[0]['title']
                book_id = response_data[0]['id']
                if not response.ok:
                    return {'message': f'Error fetching book from library: {response.status_code}'}, 500
            except Exception as e:
                return {'message': f'Error fetching book from library: {str(e)}'}, 500

            # Check loan limit for the member
            if loan_collection.count_documents({'memberName': data['memberName']}) >= 2:
                return {'message': 'You already lent 2 or more books!'}, 422

            if not check_date_format(data['loanDate']):
                return {'message': 'Unprocessable entity: Invalid date format'}, 422

            while True:
                loan_id = str(uuid.uuid4())  # generate a unique id for each user
                if users_ids.find_one({'BookID': loan_id}) is None:
                    users_ids.insert_one({'BookID': loan_id})
                    break

            loan = {
                'memberName': data['memberName'],
                'ISBN': data['ISBN'],
                "title": book_title,
                'bookID': book_id,
                'loanDate': data['loanDate'],
                'loanID': loan_id
            }
            loan_collection.insert_one(loan)
            return {'You lent the book successfully!': loan['loanID']}, 201
        except Exception as e:
            return {'Invalid JSON file': str(e)}, 422


class loanId(Resource):
    def get(self, id):
        loan = loan_collection.find_one({'loanID': id}, {'_id': 0})
        if not loan:
            return {'message': 'Loan not found'}, 404
        return loan, 200

    def delete(self, id):
        result = loan_collection.delete_one({'loanID': id})
        if result.deleted_count == 0:
            return {'message': 'Loan not found'}, 404
        return {'message': 'Loan successfully deleted', 'loanID': id}, 200  ##########


def check_date_format(date_str):
    # Check if the length of the string is either 4 (for 'yyyy') or 10 (for 'yyyy-mm-dd')
    if len(date_str) == 10:
        # Check if the first 4 characters are digits and the 5th and 8th characters are '-'
        if date_str[:4].isdigit() and date_str[4] == '-' and date_str[7] == '-':
            return True
    return False


api.add_resource(loans, "/loans")
api.add_resource(loanId, "/loans/<string:id>")

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5002, debug=True)
