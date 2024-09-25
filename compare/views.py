import openai
import json
import os
import fitz
from django.shortcuts import render, redirect
from django.core.paginator import Paginator
from django.conf import settings
from .models import Product, Price, Supermarket
from .forms import PDFUploadForm

openai.api_key = os.getenv('OPENAI_API_KEY')

def home(request):
    query = request.GET.get('search', '')
    selected_supermarket = request.GET.get('supermarket', '')
    min_price = request.GET.get('min_price', '')
    max_price = request.GET.get('max_price', '')
    sort_by = request.GET.get('sort_by', 'asc')
    results = []
    
    # Get all supermarkets for the filter dropdown
    supermarkets = Supermarket.objects.all()
    
    if query:
        # Search for products that match the query
        products = Product.objects.filter(name__icontains=query)
        
        for product in products:
            # Filter prices for the selected supermarket
            prices = Price.objects.filter(product=product)
            
            if selected_supermarket:
                prices = prices.filter(supermarket_id=selected_supermarket)
            
            # Filter by price range
            if min_price:
                prices = prices.filter(price__gte=min_price)
            if max_price:
                prices = prices.filter(price__lte=max_price)
            
            # Sort by price (ascending or descending)
            if sort_by == 'asc':
                prices = prices.order_by('price')
            else:
                prices = prices.order_by('-price')
            
            # Add results to display
            if prices.exists():
                results.append({
                    'product': product,
                    'prices': prices
                })
    
    # Pagination: Display 5 products per page
    paginator = Paginator(results, 5)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'home.html', {
        'query': query,
        'supermarkets': supermarkets,
        'results': page_obj,  # Send the paginated object
        'selected_supermarket': int(selected_supermarket) if selected_supermarket else None,
        'min_price': min_price,
        'max_price': max_price,
        'sort_by': sort_by,
        'page_obj': page_obj,  # Needed for pagination controls
    })


def upload_pdf(request):
    if request.method == 'POST':
        form = PDFUploadForm(request.POST, request.FILES)
        if form.is_valid():
            pdf_file = request.FILES['pdf_file']
            pdf_path = handle_uploaded_pdf(pdf_file)

            # Extract data from the PDF
            extracted_data = extract_text_from_pdf(pdf_path)

            # Parse data with LLM
            product_data = parse_data_with_llm(extracted_data)

            # Add extracted data to the database
            add_data_to_database(product_data)

            return redirect('home')
    else:
        form = PDFUploadForm()
    
    return render(request, 'upload_pdf.html', {'form': form})

def handle_uploaded_pdf(pdf_file):
    # Create a path inside MEDIA_ROOT/pdfs
    pdf_directory = os.path.join(settings.MEDIA_ROOT, 'pdfs')
    
    # Create the directory if it doesn't exist
    if not os.path.exists(pdf_directory):
        os.makedirs(pdf_directory)
    
    # Save the file inside the /pdfs/ directory
    pdf_path = os.path.join(pdf_directory, pdf_file.name)
    
    with open(pdf_path, 'wb+') as destination:
        for chunk in pdf_file.chunks():
            destination.write(chunk)
    
    return pdf_path

def extract_text_from_pdf(pdf_path):
    text_content = []
    
    with fitz.open(pdf_path) as pdf:
        for page_num in range(len(pdf)):
            page = pdf.load_page(page_num)
            text = page.get_text("text")
            text_content.append(text)
    
    return "\n".join(text_content)

def parse_data_with_llm(raw_text):
    # Split the text into chunks (if needed, depending on the size)
    text_chunks = split_into_chunks(raw_text, max_chunk_size=2000)
    
    all_products = []
    try:
        # Iterate through each chunk and send to the LLM
        for chunk in text_chunks:
            response = openai.ChatCompletion.create(
                model="gpt-4",  # or use another model depending on your setup
                messages=[
                    {"role": "system", "content": "You are an assistant that helps parse grocery brochures."},
                    {"role": "user", "content": f"Extract the product names, categories, and prices from the following text:\n\n{chunk}"}
                ]
            )
            
            raw_response = response['choices'][0]['message']['content']
            print("LLM Response:", raw_response)

            # Process the LLM response to extract product data
            products = parse_llm_response(raw_response)
            all_products.extend(products)
            
    except Exception as e:
        print(f"Error with OpenAI API: {e}")
    
    return all_products

def parse_llm_response(response_text):
    try:
        # Attempt to parse the response as JSON
        parsed_data = json.loads(response_text)
        return parsed_data
    except json.JSONDecodeError:
        print("Failed to parse LLM output as JSON. Raw response:", response_text)
        return []

def split_into_chunks(text, max_chunk_size):
    words = text.split()
    chunks = []
    current_chunk = []
    current_size = 0
    
    for word in words:
        if current_size + len(word) > max_chunk_size:
            chunks.append(" ".join(current_chunk))
            current_chunk = [word]
            current_size = len(word)
        else:
            current_chunk.append(word)
            current_size += len(word)
    
    if current_chunk:
        chunks.append(" ".join(current_chunk))
    
    return chunks

def add_data_to_database(product_data):
    if not isinstance(product_data, list):
        print(f"Expected a list of dictionaries but got {type(product_data)}")
        return
    
    for data in product_data:
        if isinstance(data, dict):
            product_name = data.get('name', 'Unknown Product')
            price = data.get('price', 0.0)
            category = data.get('category', 'Uncategorized')
            supermarket = data.get('supermarket', 'Unknown Supermarket')
            
            product, created = Product.objects.get_or_create(name=product_name, category=category)
            supermarket_obj, created = Supermarket.objects.get_or_create(name=supermarket)
            Price.objects.create(product=product, supermarket=supermarket_obj, price=price)
        else:
            print(f"Skipping invalid data format: {data}")