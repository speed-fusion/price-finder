import json
from pathlib import Path
import uuid
from webdriver import PlaywrightDriver
import pandas as pd
from tqdm import tqdm
import os

from dotenv import load_dotenv

load_dotenv()

class PriceFinder:
    def __init__(self) -> None:        
        
        self.username = os.environ.get("USERNAME")
        self.password = os.environ.get("PASSWORD")
        
        self.input_dir = Path("input")
        
        if not self.input_dir.exists():
            self.input_dir.mkdir()
            
        self.output_dir = Path("output")
        
        if not self.output_dir.exists():
            self.output_dir.mkdir() 
        
        self.required_cols = [
            "Street Address",
            "Suburb",
            "Postcode",
            "State"
        ]
        
        self.wd = PlaywrightDriver()
    def is_logged_in(self):
        try:
            logged_in_name = self.wd.page.wait_for_selector("//div[@id='userName']",timeout=5 * 1000).text_content()
            print(f'welcome {logged_in_name}, you are logged in.')
            return True
        except:
            return False
        
    def login(self):
        
        url = "https://www.pricefinder.com.au/portal/app?page=ExternalLogin&service=page"

        self.wd.page.goto(url)
        
        if self.is_logged_in() == True:
            return
        
        username = self.wd.page.wait_for_selector("//input[@id='inputEmail']")
        password = self.wd.page.wait_for_selector("//input[@id='inputPassword']")
        
        username.type(self.username)
        password.type(self.password)
        
        login_btn = self.wd.page.wait_for_selector("//button[@class='go']")
        login_btn.click()
        
        self.handle_terms_page()
        
        logged_in_name = self.wd.page.wait_for_selector("//div[@id='userName']").text_content()
        
        print(f'welcome {logged_in_name}, you are logged in.')
    
    def handle_terms_page(self):
        try:
            agree_btn = self.wd.page.wait_for_selector("//input[@id='ImageSubmit']",timeout=5 * 1000)
            agree_btn.click()
        except:
            pass
    
    def main(self):
        for file in self.input_dir.glob("*"):
            
            if file.is_dir() == True:
                continue
            
            status,rows = self.read_csv(file)
            
            if status == False:
                continue
            
            data = []
            self.wd.start()
            self.login()
            for prop in tqdm(rows):
                prop_copy = prop.copy()
                query = prop["query"]
                
                prop_id = self.get_property_id(query)
                prop_copy["prop_id"] = prop_id
                
                if prop_id == None:
                    data.append(prop_copy)
                    continue
                
                status,prop_info = self.get_property_info(prop_id)
                
                if status == False:
                    data.append(prop_copy)
                    continue
                
                for key in prop_info:
                    prop_copy[key] = prop_info[key]
                
                data.append(prop_copy)
            
            output_file_path = self.output_dir.joinpath(str(uuid.uuid4()) + ".csv")
            
            out_df = pd.DataFrame(data)
            
            out_df.to_csv(output_file_path,index=False)
            
            self.wd.stop()
    
    def read_csv(self,file_path):
        rows = []
        df = pd.read_csv(file_path)
        
        columns = df.columns
        
        for col in self.required_cols:
            if not col in columns:
                print(f'required column is not present in csv {col}')
                return False,None
        
        for index,row in df.iterrows():
            row_dict = row.to_dict()
            
            street = row_dict["Street Address"]
            suburb = row_dict["Suburb"]
            postcode = row_dict["Postcode"]
            state = row_dict["State"]
            
            query = f'{street}+{suburb}+{postcode}+{state}'
            
            row_dict["query"] = query
            
            rows.append(row_dict)
        
        return True,rows
    
    def get_property_info(self,prop_id):
        url = f'https://app.pricefinder.com.au/v4/api/properties/{prop_id}'
        data = {}
        try:
            self.wd.page.goto(url)
            soup = self.wd.get_soup()
            json_data = json.loads(soup.body.text)
            
            data = json_data["address"]
            
            marketStatus = json_data.get("marketStatus",None)
            
            forRent = None
            forSale = None
            
            if marketStatus != None:
                forRent = marketStatus.get("forRent",None)
                forSale = marketStatus.get("forSale",None)
            
            data["forRent"] = forRent
            data["forSale"] = forSale
            
            owners = json_data.get("owners",{})
            

            for key in owners:
                data[key] = owners[key]
        
            features = json_data.get("features",{})
            
            for key in features:
                data[key] = features[key]
            
            recentRental = json_data.get("recentRental",None)
            
            recent_rental = None
            if recentRental != None:
                if "price" in recentRental:
                    if "display" in recentRental["price"]:
                        recent_rental = recentRental["price"]["display"]
            
            data["recent_rental"] = recent_rental
            
            return True,data
            
        except:
            pass
        
        return False,data
    
    def get_property_id(self,query):
        
        url = f'https://app.pricefinder.com.au/v4/api/suggest?q={query}&currentState=&match_ids=true'
        
        try:
            self.wd.page.goto(url)
            soup = self.wd.get_soup()
            json_data = json.loads(soup.body.text)
            return json_data['matches'][0]['property']['id']
        except:
            return None

# https://app.pricefinder.com.au/v4/api/properties/1504771554 -> owners_name,org_address,street,state,postcode,suburb
# https://app.pricefinder.com.au/v4/api/suggest?q=6502%2F222+Margaret+Street%2BBrisbane+City%2B4000%2BQLD&currentState=&match_ids=true -> property_id

if __name__ == "__main__":
    pf = PriceFinder()
    pf.main()