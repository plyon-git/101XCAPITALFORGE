from supplement_collect import *

SEEDS=[
('Parikh Financial','https://parikhfinancial.com/'),
('Momentum Capital Funding','https://www.momentumcapitalfunding.com/privacy-policy/'),
('American Prudential Capital','https://www.americanprudentialcapital.com/community-guidelines/'),
('New Century Financial','https://www.newcenturyfinancial.com/contact-us/'),
('Catalyst Financial Company','https://www.catfinco.com/contact/'),
('Charter Capital Holdings','https://www.charcap.com/contact-us/'),
('DARE Capital','https://darebizcapital.com/contact/'),
('Front Range Factoring','https://frontrangefactoring.com/'),
('Match Factors','https://www.matchfactors.com/contact/'),
('Haversine Funding','https://www.haversinefunding.com/contact'),
('Orange Commercial Credit','https://www.occfactor.com/aboutus'),
('Mango Factors','https://www.mangofactors.com/'),
('SFR Business Capital','https://sfrbusinesscapital.com/'),
('Wise Business Capital','https://wisebizcap.com/contact/'),
('Factor USA Houston','https://www.factorusahouston.com/contact/'),
('R Desmond Financial Services','https://rdesfinancial-training.com/'),
('Harper Partners','https://www.joinharper.com/'),
]
if __name__=='__main__':
    recs=[]
    with concurrent.futures.ThreadPoolExecutor(8) as pool:
        for r in pool.map(crawl_site,[{'name':n,'website':u,'source_url':u,'source_name':'Official public commercial finance website'} for n,u in SEEDS]):
            r['category']='factoring_receivables';r['deal_fit_status']='business_receivables_mandate_unconfirmed';r['property_collateral_fit']='no_property_collateral_mandate_unconfirmed';r['country']='US';recs.append(r)
    explicit={
      'Parikh Financial':('admin@parikhfinancial.com','832-649-8275','https://parikhfinancial.com/'),
      'American Prudential Capital':('info@americanprudentialcapital.com','713-352-7088','https://www.americanprudentialcapital.com/community-guidelines/'),
      'New Century Financial':('info@newcenturyfinancial.com','800-805-8380','https://www.newcenturyfinancial.com/contact-us/'),
      'Front Range Factoring':('info@frontrangefactoring.com','303-219-3914','https://frontrangefactoring.com/'),
      'Match Factors':('Admin@MatchFactors.com','800-738-9591','https://www.matchfactors.com/contact/'),
      'Mango Factors':('info@mangofactors.com','516-399-1806','https://www.mangofactors.com/'),
      'SFR Business Capital':('info@sfrbusinesscapital.com','615-419-2066','https://sfrbusinesscapital.com/'),
      'Wise Business Capital':('info@wisebizcap.com','618-952-1300','https://wisebizcap.com/contact/'),
    }
    for r in recs:
        if r['name'] in explicit:
            r['email'],r['phone'],src=explicit[r['name']];r['email_source_url']=src;r['phone_source_url']=src
        if r['name'] in ['Mango Factors','SFR Business Capital','Wise Business Capital','Factor USA Houston','R Desmond Financial Services']:
            r['category']='commercial_finance_broker_referral';r['deal_fit_status']='broker_referral_not_direct_capital'
        if r['name']=='Haversine Funding':r['deal_fit_status']='specialty_lender_finance_mismatch';r['description']='Official site says it finances specialty lenders, not borrowers; potential capital network referral only. '+r['description']
        if r['name']=='Parikh Financial' or r['name']=='Match Factors':r['deal_fit_status']='trucking_receivables_industry_mismatch'
        r['contact_status']='phone_and_email_public' if r['phone'] and r['email'] else 'partial_contact' if r['phone'] or r['email'] else 'contacts_missing'
    open(os.path.join(ROOT,'supplement_ifa.jsonl'),'w').write(''.join(json.dumps(r)+'\n' for r in recs))
    print('IFA supplemental',len(recs),'complete',sum(bool(r['phone'] and r['email']) for r in recs),flush=True)
