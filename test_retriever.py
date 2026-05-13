import sys
sys.path.append(".")  # makes sure project imports work

from services.retriever import load_qa, retrieve

qa = load_qa()
test_questions = [
    "my baby is 1 year old not eating anything what should i do",
]

print("\n" + "="*70)
for q in test_questions:
    score, results = retrieve(q, qa)
    top_match = results[0]['question'] if results else "none"
    print(f"\nQuery : {q}")
    print(f"Score : {score:.3f}")
    print(f"Match : {top_match}")
    print("-"*70)