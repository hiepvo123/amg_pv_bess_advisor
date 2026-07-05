import os
import zipfile
import glob
import shutil

DATA_DIR = "../data"
OUTPUT_DIR = "../static/diagrams"

def extract_images_from_docx():
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
        
    docx_files = glob.glob(os.path.join(DATA_DIR, "*.docx"))
    
    if not docx_files:
        print("Khong tim thay file .docx trong thu muc data.")
        return

    img_count = 0
    for docx_path in docx_files:
        print(f"Dang xu ly file: {docx_path}")
        # docx is essentially a zip file
        with zipfile.ZipFile(docx_path, 'r') as zip_ref:
            for file_info in zip_ref.infolist():
                if file_info.filename.startswith('word/media/'):
                    # Extract image
                    zip_ref.extract(file_info, path="./temp_extract")
                    
                    # Move to static folder and rename based on docx name
                    extracted_path = os.path.join("./temp_extract", file_info.filename)
                    base_name = os.path.basename(docx_path).replace(".docx", "")
                    img_name = os.path.basename(file_info.filename)
                    new_filename = f"{base_name}_{img_name}"
                    new_path = os.path.join(OUTPUT_DIR, new_filename)
                    
                    shutil.move(extracted_path, new_path)
                    img_count += 1
                    
    # Clean up temp dir
    if os.path.exists("./temp_extract"):
        shutil.rmtree("./temp_extract")
        
    print(f"Da trich xuat {img_count} hinh anh vao thu muc {OUTPUT_DIR}")

if __name__ == "__main__":
    extract_images_from_docx()
