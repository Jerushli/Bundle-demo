
import argparse, json
from backend.input_file_classifier import classify_csv_file, persist_classification

def main():
    p=argparse.ArgumentParser()
    p.add_argument("file_path")
    p.add_argument("--sample-rows",type=int,default=200)
    p.add_argument("--dataset-name",default=None)
    p.add_argument("--persist",action="store_true")
    a=p.parse_args()
    result=classify_csv_file(a.file_path,sample_rows=a.sample_rows)
    if a.persist:
        result=persist_classification(result,dataset_name=a.dataset_name,created_by="cli")
    print(json.dumps(result,indent=2,default=str))

if __name__=="__main__":
    main()
