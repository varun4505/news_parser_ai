from googlenewsdecoder import new_decoderv1

def main():

    source_url = "https://news.google.com/rss/articles/CBMitgFBVV95cUxOcWstUEZDbmRxVkdjc053ZUpNc1R0VlB1bjc0Vkxwbm9YNUVrRzg3TVVhS3NLY2VEOWxNeEx5akhjRkxOTHJ3MkdTR2RIQ0EzcFQtUTB6UW9WUEpGcEl2NmI5NkhYTlpsVWdsRV9TNGx0YWNweDdJbVU4RGFqMHgxOVgyYlFmamZScl9zbHh5RGN0ZF9xMDBfVnJ3VlZrM1lsQnZzMGVoem1jMm5kNENpNzNFdURWUdIBuwFBVV95cUxNMmNCcGQ2VlQ0MUh1bFVIYWlCaDJiTHJiS2pyMENxU2NyQkc1cWhoeER2NmNuVXRPcFpUSFJUYWFVOHBhSEtuUkNLNlF4Vk9GOUNSek5sRklRaXJMYmZ2Y0xvY2lMZG85aWh0alF5dnNiODRoY3l1OEZ5RFFyRDdybkRaN0xtOTBmNDl3MVJLUTB5RGJaaFQ3U0xtODB1UENXZ21yWnY4Uk9vQ08yT3d2VWlKNm81SXdUNG4w?oc=5&hl=en-US&gl=US&ceid=US:en"

    try:
        decoded_url = new_decoderv1(source_url)

        if decoded_url.get("status"):
            print("Decoded URL:", decoded_url["decoded_url"])
        else:
            print("Error:", decoded_url["message"])
    except Exception as e:
        print(f"Error occurred: {e}")

if __name__ == "__main__":
    main()