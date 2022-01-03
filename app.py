# Frontend and web framework
from flask import Flask, render_template, request, session, redirect, flash, send_file
from flask.helpers import total_seconds
from flask_bootstrap import Bootstrap
import os, json
from werkzeug.utils import secure_filename

# Flask configuration
app = Flask(__name__)
Bootstrap(app)
app.secret_key = 'dljsaklqk24e21cjn!Ew@@dsa5'
app.config['TEMPLATES_AUTO_RELOAD'] = True

# S3 config
AWS_BUCKET_NAME = 'cheekybucket'
AWS_ACCESS_KEY = 'AKIA2G3PNNUOCXY7HX72' 
AWS_SECRET_ACCESS_KEY = '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'
AWS_DOMAIN = 'http://cheekybucket.s3.amazonaws.com/'

# Backend
from os import error
from random import randrange
from pandas.core.base import NoNewAttributesMixin
import requests
from bs4 import BeautifulSoup
import datetime
import pandas as pd
import numpy as np
import re
import akshare as ak
import matplotlib.pyplot as plt
import matplotlib
import locale
matplotlib.use('Agg')

import boto3, botocore

s3 = boto3.client(
    "s3",
    aws_access_key_id=os.getenv('AWS_ACCESS_KEY'),
    aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY')
)

def upload_file_to_s3(file, acl="public-read"):
    filename = secure_filename(file.filename)
    try:
        s3.upload_fileobj(
            file,
            os.getenv("AWS_BUCKET_NAME"),
            file.filename,
            ExtraArgs={
                "ACL": acl,
                "ContentType": file.content_type
            }
        )

    except Exception as e:
        # This is a catch all exception, edit this part to fit your needs.
        print("Something Happened: ", e)
        return e
    

    # after upload file to s3 bucket, return filename of the uploaded file
    return file.filename

'''
Web scraper for repurchase data
Input: Number of days 
Output: All recent repurchase data
'''
def get_repurchase_raw_data(day): 
    ''' Get repurchase raw data from HKEX

    res=requests.get("https://www.hkexnews.hk/reports/sharerepur/sbn.asp")
    soup=BeautifulSoup(res.text,"html.parser")

    main_data=soup.find("table").find_all("td")
    lst=[]
    for data in main_data:
        try:
            url=data.find("a").get('href')[1:]
            main_url="https://www.hkexnews.hk/reports/sharerepur"+url
            print(url)
            lst.append(main_url)
        except AttributeError:
            pass
    '''
    start = datetime.datetime.now() - datetime.timedelta(day)
    end = datetime.datetime.now()
    dates = pd.bdate_range(start, end)
    column_name = ['Stock', 'Code', 'Sec_type', 'Date', 'Num_sec', 'Highest_price', 'Lowest_price', 'Total_paid', 'Method', 'Number_of_sec_purchased', 'Perc_number_of_shares_issue']
    output_df = pd.DataFrame()

    for date in dates:
        try:
            # Extract excel file from hkex
            end = str(date).split()[0].replace('-','')
            main_url = "https://www.hkexnews.hk/reports/sharerepur/documents/SRRPT" + end + '.xls'
            resp=requests.get(main_url)
            output = open("tmp/{}.xls".format(end), 'wb')
            output.write(resp.content)
            temp_df = pd.read_excel("tmp/{}.xls".format(end))

            # Get the index that matches my condition
            temp_df = temp_df.loc[temp_df['Unnamed: 1'] < '9999999']
            output_df = output_df.append(temp_df)
            output.close()
        except:
            pass

    # Change name
    output_df = output_df.rename(columns={'Unnamed: 0': 'Stock', 'Unnamed: 1': 'Code', 'Unnamed: 2': 'Sec_type', 'Unnamed: 3': 'Date', 
                    'Unnamed: 4': 'Num_sec', 'Unnamed: 5': 'Highest_price', 'Unnamed: 6': 'Lowest_price', 'Unnamed: 7': 'Total_paid', 
                    'Unnamed: 8': 'Method', 'Unnamed: 9' :'Number_of_sec_purchased', 'Unnamed: 10' :'Perc_number_of_shares_issue'})

    return output_df, dates
    
'''
Extract repurchase information for single stock
Input: Stock ticker, dataset, number of recent day
Output: Single stock repurchase information
'''
def single_name_information(ticker, df, day):
    '''
    Extract repurchase information for a single stock
    including total repurchase stock, average repurchase price and percentage to common shares
    '''
    single_name_df = pd.DataFrame()
    single_name_df = df.loc[df['Code'] == str(ticker)]
    if single_name_df.empty:
        return None, 0
    # Get repurchase info
    Total_shares, Total_paid, Currency = 0, 0, ''
    for index, row in single_name_df.iterrows():
        row['Num_sec'] = int(str(row['Num_sec']).replace(',',''))
        Total_shares = Total_shares + row['Num_sec']
        Currency = row['Total_paid'].split(" ")[0]
        Total_paid = Total_paid + int(row['Total_paid'].split(" ")[1].split(".")[0].replace(',',''))
        row['Date'] = row['Date'].split()[0].replace('/','-')
    
    common_share = float(single_name_df.tail(1)["Number_of_sec_purchased"].iloc[0].replace(',',''))/(float(single_name_df.tail(1)["Perc_number_of_shares_issue"].iloc[0])*0.01)
    print(common_share)

    # Get latest repurchase info
    summary = "在{}天内，{}一共回购了{}股，平均回购股价为{} - 共{}元, 占流通股{}%".format(day, single_name_df['Stock'].iloc[0], f"{Total_shares:,}"
    , round(Total_paid/Total_shares,2), f"{Total_paid:,}", round(Total_shares/common_share,5))
    return single_name_df, summary
    

'''
Extract stock data information 
Input: Stock ticker, dates
Output: Single stock repurchase information
'''
def get_share_data(ticker, dates):
    try:
        input_ticker = str(ticker).zfill(5)
        start = str(dates[0]).split()[0].replace('-','')
        end = str(dates[-1]).split()[0].replace('-','')
        stock_hk_hist_df = ak.stock_hk_hist(symbol=input_ticker, start_date=start, end_date=end, adjust="")
        stock_hk_hist_df = stock_hk_hist_df.rename(columns={'日期': 'Date'})
        return stock_hk_hist_df
    except:
        return None


'''
Get summarise graph based on repurchase data and stock price
'''
def get_repurchase_and_price(repurchase_data, share_data, dates):

    # Share price and repurchase amount
    date_num_stock_dict = {}
    for index, row in share_data.iterrows():
        date_num_stock_dict[row['Date']] = 0
    for index, row in repurchase_data.iterrows():
        date_num_stock_dict[row['Date']] = row['Num_sec']

    # Plot price vs repurchase data
    
    plt.figure(2)
    fig, axs = plt.subplots(2)
    axs[0].bar(*zip(*sorted(date_num_stock_dict.items())), alpha = 0.2)
    plt.ylabel("Share Closing Price")
    axs[1].plot(share_data['Date'], share_data['收盘'])
    plt.xlabel("Date")
    plt.xticks(fontsize=7, rotation=90)
    plt.ylabel("Share Closing Price")
    plt.tight_layout()
    random = randrange(1000) 
    plt.setp(axs[0].get_xticklabels(), visible=False)
    plt.savefig('static/'+str(random) + 'price_repurchase_history.png', dpi=80)
    return 'static/'+str(random) + 'price_repurchase_history.png'
    

'''
Pre-process industry data
'''
def get_industry_data():
    raw_industry_df = pd.read_csv('static/HKEX_BY_INDUSTRY.csv')  
    raw_industry_df = raw_industry_df.rename(columns={"Unnamed: 3": "Ticker"})
    for i in raw_industry_df.index:
        code = re.findall(r'\d+', raw_industry_df.at[i, 'Stock'])
        raw_industry_df.at[i, 'Ticker'] = code[-1]
        raw_industry_df.at[i, 'Stock'] = raw_industry_df.at[i, 'Stock'].split("(")[0]
    return raw_industry_df
    
'''
Obtain industry summary within same name
'''
def get_stock_industry_summary(ticker, industry_data, raw_repurchase_data):
    
    industry_df = industry_data
    repurchase_df = raw_repurchase_data
    repurchase_df['Code'] = repurchase_df['Code'].astype(float, errors = 'raise')
    industry_df['sum'] = 0
    new_df = industry_data[industry_data['Ticker'].isin(raw_repurchase_data['Code'])]
    # Transform total paid string
    paid_list = []
    for index, row in repurchase_df.iterrows():
        try:
            paid_list.append(float(row['Total_paid'].split(" ")[1].replace(',','')))
        except IndexError:
            paid_list.append(0)
    repurchase_df['Total_paid'] = paid_list
    
    # Transform aggregate sum
    aggregate_sum = []
    for index, row in new_df.iterrows():
        sum = repurchase_df.loc[repurchase_df['Code'] == row['Ticker'], 'Total_paid'].sum()
        aggregate_sum.append(sum)
    new_df['Total_paid'] = aggregate_sum
    
    # Get sector summary
    sector = new_df.loc[new_df['Ticker'] == ticker]['Sector'].iloc[0]
    num_names = len(industry_df.loc[industry_df['Sector'] == sector]['Stock'])
    Name = new_df.loc[new_df['Ticker'] == ticker]['Stock'].iloc[0]
    sector_df = new_df.loc[new_df['Sector'] == sector]
    num_repurchase, sector_average = len(sector_df.index), sector_df['Total_paid'].mean()
    
    # Create chart
    fig, ax1 = plt.subplots(1, 1, sharey=True)
    pos1 = np.arange(num_repurchase)
    ax1.bar(pos1,sector_df['Total_paid'])
    plt.sca(ax1)
    plt.xticks(pos1,sector_df['Stock'])
    plt.xticks(fontsize=7, rotation=90)
    plt.ylabel("Company repurchase sum")
    plt.tight_layout()
    random = randrange(1000) 
    plt.savefig('static/'+str(random) + 'stock_sector_summary.png')
    return new_df, num_repurchase, sector_average, Name, sector, 'static/'+str(random) + 'stock_sector_summary.png', num_names

'''
Create heatmap for industry comparison
'''
def get_entire_industry_summary(df):
    sectors = df['Sector'].unique()
    sector_summary_df = pd.DataFrame()
    sector_summary_df['Sector'] = sectors

    sector_sum = []
    for index, row in sector_summary_df.iterrows():
        row['Sector']
        temp_sum = df.loc[df['Sector'] == row['Sector'], 'Total_paid'].sum()
        sector_sum.append(temp_sum)
    sector_summary_df['sum'] = sector_sum
    sector_summary_df = sector_summary_df.sort_values(by ='sum', ascending=False).head(10)

    # Create chart
    fig, ax1 = plt.subplots(1, 1, sharey=True)
    pos1 = np.arange(len(sector_summary_df.index))
    ax1.bar(pos1,sector_summary_df['sum'])
    plt.sca(ax1)
    plt.xticks(pos1,sector_summary_df['Sector'])
    plt.xticks(fontsize=7, rotation=90)
    plt.ylabel("Industry repurchase sum")
    plt.tight_layout()
    random = randrange(1000) 
    plt.savefig('static/'+str(random) + 'sector_summary.png')
    return 'static/'+str(random) + 'sector_summary.png', sector_summary_df.head(1)['Sector'].iloc[0]

@app.route('/')
def index():
    # Delete all previously store image
    return render_template('index.html')

@app.route('/restart', methods=['POST','GET']) 
def restart():
    for filename in os.listdir("static"):
        if filename.endswith('png'):
            os.remove("static/"+filename)
    for filename in os.listdir("tmp"):
        os.remove("tmp/"+filename)
    
    return render_template('index.html')


@app.route('/summary', methods=['POST'])
def summary():
    if request.method == 'POST':
        ticker = request.form['stock']
        day = request.form['day']
        raw_df, dates = get_repurchase_raw_data(int(day))
        stock_repurchase_data, summary = single_name_information(int(ticker), raw_df, int(day))
        if summary == 0:
            flash("No repurchase history found for '{}' in the past {} days".format(int(ticker), int(day)))
            return redirect('/')
        share_data = get_share_data(int(ticker), dates)
        photo1 = get_repurchase_and_price(stock_repurchase_data, share_data, dates)
        raw_industry = get_industry_data()
        industry_df, num_repurchase, sector_average, stock_name, sector, photo2, num_names = get_stock_industry_summary(int(ticker), raw_industry, raw_df)

        photo3, highest_industry = get_entire_industry_summary(industry_df)
        return render_template('summary.html', stock_repurchase_data = stock_repurchase_data.to_html(), summary=summary, 
            num_repurchase = num_repurchase, sector_average = f"{int(sector_average):,}", stock_name = stock_name, sector = sector, photo1 = photo1,
            photo2 = photo2, photo3 = photo3, highest_industry = highest_industry, num_names = num_names)

if __name__ == "__main__":
    app.run(debug=True, threaded=True)







