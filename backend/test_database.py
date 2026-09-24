from database import get_database_connection


def test_connection():

    try:

        with get_database_connection() as connection:

            with connection.cursor() as cursor:

                cursor.execute(
                    "SELECT COUNT(*) FROM orders;"
                )

                result = cursor.fetchone()

                print("Database connected successfully!")

                print(
                    f"Total orders: {result[0]}"
                )

    except Exception as error:

        print("Database connection failed!")

        print(type(error).__name__)

        print(error)


if __name__ == "__main__":

    test_connection()