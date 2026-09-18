import { useState } from 'react'
import { Route, Routes } from 'react-router-dom'
import { Banner } from './components/Banner/Banner'
import { ConsentGate } from './components/ConsentGate/ConsentGate'
import { Footer } from './components/Footer/Footer'
import { Header } from './components/Header/Header'
import { ProfilePanel } from './components/ProfilePanel/ProfilePanel'
import { ReducedCaptureNotice } from './components/ReducedCaptureNotice/ReducedCaptureNotice'
import { CartProvider } from './state/CartContext'
import { PrismSDKProvider } from './state/PrismSDKContext'
import { useSession } from './state/SessionContext'
import { WishlistProvider } from './state/WishlistContext'
import { Cart } from './pages/Cart/Cart'
import { Category } from './pages/Category/Category'
import { Checkout } from './pages/Checkout/Checkout'
import { Compare } from './pages/Compare/Compare'
import { DeleteMyData } from './pages/DeleteMyData/DeleteMyData'
import { Detail } from './pages/Detail/Detail'
import { Home } from './pages/Home/Home'
import { NotFound } from './pages/NotFound/NotFound'
import { Search } from './pages/Search/Search'
import { WhatGetsRecorded } from './pages/WhatGetsRecorded/WhatGetsRecorded'

function App() {
  const { consent } = useSession()
  const [profileOpen, setProfileOpen] = useState(false)

  if (consent === 'unset') {
    return <ConsentGate />
  }

  return (
    <PrismSDKProvider>
      <CartProvider>
        <WishlistProvider>
          <a href="#main" className="skip-link">
            Skip to content
          </a>
          <Banner />
          <ReducedCaptureNotice />
          <Header onOpenProfile={() => setProfileOpen(true)} />
          <main id="main">
            <Routes>
              <Route path="/" element={<Home />} />
              <Route path="/category/:category" element={<Category />} />
              <Route path="/search" element={<Search />} />
              <Route path="/item/:itemId" element={<Detail />} />
              <Route path="/compare/:setId" element={<Compare />} />
              <Route path="/cart" element={<Cart />} />
              <Route path="/checkout" element={<Checkout />} />
              <Route path="/what-gets-recorded" element={<WhatGetsRecorded />} />
              <Route path="/delete-my-data" element={<DeleteMyData />} />
              <Route path="*" element={<NotFound />} />
            </Routes>
          </main>
          <Footer />
          <ProfilePanel open={profileOpen} onClose={() => setProfileOpen(false)} />
        </WishlistProvider>
      </CartProvider>
    </PrismSDKProvider>
  )
}

export default App
