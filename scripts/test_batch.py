from tasks.batch_extraction import call_gemini_batch, validate_batch

complaints = [
    {"id": "c1", "text": "Sadak bahut kharab hai, teen mahine se gaddha hai, Lucknow mein"},
    {"id": "c2", "text": "There is no streetlight on our road, its very dark at night"},
    {"id": "c3", "text": "Humare mohalle mein bijli roz 4-5 ghante cut rehta hai"},
    {"id": "c4", "text": "Water supply in Pune has been cut off for 5 days, people are suffering badly"},
    {"id": "c5", "text": "Garbage has not been collected in our street for two weeks, Kanpur Nagar"},
    {"id": "c6", "text": "The primary health centre has no doctor, patients are turned away"},
]

valid_districts = ["lucknow", "pune", "kanpur nagar", "hyderabad"]  # sample list for now

raw = call_gemini_batch(complaints)
good, bad = validate_batch([c["id"] for c in complaints], raw, valid_districts)

print("ACCEPTED:")
for k, v in good.items():
    print(" ", k, v)
print("REJECTED:", bad)
