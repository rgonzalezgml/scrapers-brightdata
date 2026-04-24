
const base_url = 'https://global.oliveyoung.com/display/page/best-seller';
// const base_url_2 = "https://global.oliveyoung.com/?rwardCode=ARSHIA123&utm_source=influencers&guestId=af17e2ef-fbab-4e88-ab61-d863e0aead17&isMyAccountEditAddressInputConditionOverrideGateOn=true&isRecommendationSectionFeatureOn=true&isWebShareApiTestFeatureOn=false&isReactHomeSectionGateOn=false&isDisplayPriceRangeUiFeatureOn=true&isAmplitudeUtmImprovementFeatureOn=true&isCpnMaxDiscountValueGateOn=true&isJpOrderPhoneValidationGateOn=true&isNewPdpFreeGiftsApiFeatureOn=false&cornerOrderExperiment=%5B%22bestSeller%22%2C%22chosenForYou%22%2C%22featuredBrands%22%2C%22ourPicks%22%2C%22recommendationMD%22%2C%22brandVideo%22%2C%22kpop%22%5D&isAfPurchaseEventChangeFeatureOn=true&isForceUpdateAndroidGateOn=false&isGa4QuantityNumberTypeGateOn=true&isAmplitudeTrackingOptionsGateOn=true";
// const url = new URL(base_url_2 || input.url || base_url);

const url = new URL(base_url);
// country('kr');

// country('us');

navigate(url);

wait('.nav-item.nbs-tab-item');

const region = input.region || 'usa';

if (region.toLowerCase() === 'korea') {
  if (!el_exists('#pillsTab1Nav2.active')) {
    click('#pillsTab1Nav2');
    wait('#pillsTab1Cont2');
  }
  scroll_to('bottom');
} else {
  if (!el_exists('#pillsTab1Nav1.active')) {
    click('#pillsTab1Nav1');
    wait('#pillsTab1Cont1');
  }
  scroll_to('bottom');
}

const data = parse();
const { product_urls } = data;

console.log(`Found ${product_urls.length} product URLs for region: ${region}`);

for (let product_url of product_urls) {
  next_stage({ url: product_url, region: input.region ?? 'usa' });
}
